from __future__ import annotations

import base64
import mimetypes
import os
import threading
import time
from copy import deepcopy
from pathlib import Path
from queue import Empty, Queue
from typing import Any

import fal_client
import requests

from app.core.config import settings


OPENAI_MAX_RETRIES = 3
OPENAI_RETRY_STATUS_CODES = {500, 502, 503, 504, 520}


def summarize_response_text(response: requests.Response, limit: int = 1200) -> str:
    text = response.text.strip()
    if not text:
        return "<empty response body>"
    if len(text) <= limit:
        return text
    return f"{text[:limit]}... [truncated]"


def infer_extension(output_format: str | None, content_type: str | None) -> str:
    if output_format:
        normalized = output_format.lower()
        if normalized == "jpeg":
            return "jpg"
        return normalized
    if content_type:
        guessed = mimetypes.guess_extension(content_type.split(";", 1)[0].strip())
        if guessed:
            return guessed.lstrip(".").replace("jpe", "jpg")
    return "png"


class ImageGenerationService:
    def generate(self, model: dict[str, Any], image_path: Path, prompt: str) -> dict[str, Any]:
        if model["provider"] == "openai" and model["id"] == "openai:gpt-image-2:edit":
            return self._call_openai_image_edit(model, image_path, prompt)
        if model["provider"] == "fal" and model["id"] in {
            "fal:fal-ai/nano-banana-2/edit",
            "fal:fal-ai/flux-2-pro/edit",
            "fal:fal-ai/flux-pro/kontext",
            "fal:fal-ai/bytedance/seedream/v5/lite/edit",
            "fal:ideogram/v4/image-to-image",
            "fal:xai/grok-imagine-image/edit",
        }:
            return self._call_fal_image_edit(model, image_path, prompt)
        raise ValueError(
            f"Real execution is not yet supported for model '{model['id']}'. "
            "Use mock mode or select one of the supported real-execution models."
        )

    def _encode_image_as_data_uri(self, image_path: Path) -> str:
        mime_type = mimetypes.guess_type(image_path.name)[0] or "application/octet-stream"
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"

    def _deep_get(self, data: Any, path: list[Any]) -> Any:
        current = data
        for key in path:
            if isinstance(key, int):
                if not isinstance(current, list) or key >= len(current):
                    return None
                current = current[key]
            else:
                if not isinstance(current, dict) or key not in current:
                    return None
                current = current[key]
        return current

    def _render_template_value(self, value: Any, substitutions: dict[str, str]) -> Any:
        if isinstance(value, str):
            rendered = value
            for key, replacement in substitutions.items():
                rendered = rendered.replace(f"{{{key}}}", replacement)
            return rendered
        if isinstance(value, list):
            return [self._render_template_value(item, substitutions) for item in value]
        if isinstance(value, dict):
            return {
                key: self._render_template_value(item, substitutions)
                for key, item in value.items()
            }
        return value

    def _call_openai_image_edit(
        self,
        model: dict[str, Any],
        image_path: Path,
        prompt: str,
    ) -> dict[str, Any]:
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required for real OpenAI execution.")

        defaults = deepcopy(model["defaults"])
        params = deepcopy(model["request"]["params"])
        payload: dict[str, Any] = {
            "model": params["model"],
            "prompt": prompt,
        }

        for key in ("size", "quality", "output_format", "background"):
            value = defaults.get(key)
            if value is not None:
                payload[key] = value
        if defaults.get("output_compression") is not None:
            payload["output_compression"] = str(defaults["output_compression"])

        mime_type = mimetypes.guess_type(image_path.name)[0] or "application/octet-stream"
        image_size_bytes = image_path.stat().st_size
        prompt_length = len(prompt)
        print(
            "OpenAI image edit request prepared:"
            f" model={payload['model']},"
            f" image={image_path.name},"
            f" mime={mime_type},"
            f" image_size_bytes={image_size_bytes},"
            f" prompt_chars={prompt_length},"
            f" output_format={payload.get('output_format')},"
            f" quality={payload.get('quality')},"
            f" size={payload.get('size')}"
        )

        response: requests.Response | None = None
        last_exception: Exception | None = None
        request_started = time.perf_counter()
        for attempt in range(1, OPENAI_MAX_RETRIES + 1):
            attempt_started = time.perf_counter()
            try:
                with image_path.open("rb") as image_file:
                    files = {
                        model["request"]["input_image_field"]: (
                            image_path.name,
                            image_file,
                            mime_type,
                        )
                    }
                    response = requests.post(
                        "https://api.openai.com/v1/images/edits",
                        headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                        data=payload,
                        files=files,
                        timeout=180,
                    )

                attempt_elapsed = time.perf_counter() - attempt_started
                request_id = response.headers.get("x-request-id") or response.headers.get("request-id")
                print(
                    "OpenAI image edit response:"
                    f" attempt={attempt}/{OPENAI_MAX_RETRIES},"
                    f" status={response.status_code},"
                    f" elapsed_s={attempt_elapsed:.2f}"
                    + (f", request_id={request_id}" if request_id else "")
                )

                if response.status_code in OPENAI_RETRY_STATUS_CODES and attempt < OPENAI_MAX_RETRIES:
                    sleep_seconds = attempt * 2
                    print(
                        "OpenAI image edit retry scheduled:"
                        f" status={response.status_code},"
                        f" sleep_s={sleep_seconds},"
                        f" body={summarize_response_text(response, limit=300)}"
                    )
                    time.sleep(sleep_seconds)
                    continue
                break
            except requests.exceptions.RequestException as exc:
                last_exception = exc
                attempt_elapsed = time.perf_counter() - attempt_started
                print(
                    "OpenAI image edit transport error:"
                    f" attempt={attempt}/{OPENAI_MAX_RETRIES},"
                    f" elapsed_s={attempt_elapsed:.2f},"
                    f" error={exc}"
                )
                if attempt >= OPENAI_MAX_RETRIES:
                    raise RuntimeError(f"OpenAI request failed after {attempt} attempts: {exc}") from exc
                sleep_seconds = attempt * 2
                print(f"OpenAI image edit transport retry scheduled: sleep_s={sleep_seconds}")
                time.sleep(sleep_seconds)

        if response is None:
            if last_exception is not None:
                raise RuntimeError(f"OpenAI request failed: {last_exception}") from last_exception
            raise RuntimeError("OpenAI request did not produce a response.")

        if response.status_code >= 400:
            raise RuntimeError(
                f"OpenAI image edit failed with HTTP {response.status_code}: "
                f"{summarize_response_text(response)}"
            )

        body = response.json()
        data = body.get("data") or []
        if not data:
            raise RuntimeError(f"OpenAI response did not include image data: {body}")

        image_item = data[0]
        if "b64_json" not in image_item:
            raise RuntimeError(f"OpenAI response did not include b64_json: {body}")

        decode_started = time.perf_counter()
        image_bytes = base64.b64decode(image_item["b64_json"])
        decode_elapsed = time.perf_counter() - decode_started
        extension = infer_extension(payload.get("output_format"), None)
        total_elapsed = time.perf_counter() - request_started
        print(
            "OpenAI image edit completed:"
            f" total_elapsed_s={total_elapsed:.2f},"
            f" decode_elapsed_s={decode_elapsed:.3f},"
            f" output_bytes={len(image_bytes)},"
            f" extension={extension}"
        )
        return {
            "image_bytes": image_bytes,
            "extension": extension,
            "generation_elapsed_s": total_elapsed,
            "provider_elapsed_s": total_elapsed,
            "download_elapsed_s": 0.0,
            "request_payload": payload,
            "raw_response": body,
        }

    def _call_fal_image_edit(
        self,
        model: dict[str, Any],
        image_path: Path,
        prompt: str,
    ) -> dict[str, Any]:
        if not settings.fal_api_key:
            raise RuntimeError("FAL_KEY is required for real FAL execution.")

        os.environ["FAL_KEY"] = settings.fal_api_key
        input_image_url = self._encode_image_as_data_uri(image_path)
        request_template = self._render_template_value(
            deepcopy(model["request"]["arguments_template"]),
            {
                "prompt": prompt,
                "input_image_url": input_image_url,
            },
        )

        print(
            "FAL image edit request prepared:"
            f" model={model['request']['model_path']},"
            f" image={image_path.name},"
            f" prompt_chars={len(prompt)},"
            f" output_format={request_template.get('output_format')},"
            f" resolution={request_template.get('resolution')},"
            f" image_size={request_template.get('image_size')}"
        )

        provider_started = time.perf_counter()
        handler = fal_client.submit(
            model["request"]["model_path"],
            arguments=request_template,
        )
        print(
            "FAL image edit submitted; waiting for result."
            f" timeout_s={settings.fal_result_timeout_seconds}"
        )
        result = self._wait_for_fal_result(handler, settings.fal_result_timeout_seconds)
        provider_elapsed = time.perf_counter() - provider_started
        print(f"FAL image edit result received: elapsed_s={provider_elapsed:.2f}")

        image_url = None
        for path in model["response"]["image_url_paths_priority"]:
            image_url = self._deep_get(result, path)
            if image_url:
                break
        if not image_url:
            raise RuntimeError(f"FAL response did not include an image URL: {result}")

        download_started = time.perf_counter()
        download_response = requests.get(image_url, timeout=180)
        download_elapsed = time.perf_counter() - download_started
        print(
            "FAL image downloaded:"
            f" status={download_response.status_code},"
            f" elapsed_s={download_elapsed:.2f}"
        )
        download_response.raise_for_status()

        extension = infer_extension(
            request_template.get("output_format"),
            download_response.headers.get("Content-Type"),
        )
        total_elapsed = provider_elapsed + download_elapsed
        print(
            "FAL image edit completed:"
            f" total_elapsed_s={total_elapsed:.2f},"
            f" provider_elapsed_s={provider_elapsed:.2f},"
            f" download_elapsed_s={download_elapsed:.2f},"
            f" output_bytes={len(download_response.content)},"
            f" extension={extension}"
        )
        return {
            "image_bytes": download_response.content,
            "extension": extension,
            "generation_elapsed_s": total_elapsed,
            "provider_elapsed_s": provider_elapsed,
            "download_elapsed_s": download_elapsed,
            "request_payload": request_template,
            "raw_response": result,
        }

    def _wait_for_fal_result(self, handler: Any, timeout_seconds: int) -> Any:
        result_queue: Queue[tuple[bool, Any]] = Queue(maxsize=1)

        def worker() -> None:
            try:
                result_queue.put((True, handler.get()))
            except Exception as exc:
                result_queue.put((False, exc))

        thread = threading.Thread(target=worker, name="fal-result-wait", daemon=True)
        thread.start()

        try:
            ok, payload = result_queue.get(timeout=timeout_seconds)
        except Empty as exc:
            raise RuntimeError(
                f"FAL result wait timed out after {timeout_seconds}s."
            ) from exc

        if ok:
            return payload
        raise RuntimeError(f"FAL result wait failed: {payload}") from payload
