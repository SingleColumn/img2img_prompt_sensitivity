from __future__ import annotations

from typing import Any


# Frontend-safe model metadata. Provider request details remain backend-owned.
MODELS: list[dict[str, Any]] = [
    {
        "id": "openai:gpt-image-2:edit",
        "provider": "openai",
        "display_name": "GPT Image 2 Edit",
        "description": "OpenAI image edit model for prompt-driven image-to-image edits.",
        "api_key_env": "OPENAI_API_KEY",
        "request": {
            "endpoint": "/v1/images/edits",
            "input_image_field": "image",
            "params": {
                "model": "gpt-image-2",
            },
        },
        "defaults": {
            "size": "auto",
            "quality": "auto",
            "output_format": "png",
            "output_compression": None,
            "background": "auto",
        },
    },
    {
        "id": "fal:fal-ai/nano-banana-2/edit",
        "provider": "fal",
        "display_name": "Nano Banana 2 Edit",
        "description": "FAL-hosted image edit model based on Nano Banana 2.",
        "api_key_env": "FAL_KEY",
        "request": {
            "model_path": "fal-ai/nano-banana-2/edit",
            "input_image_field": "image_urls",
            "arguments_template": {
                "prompt": "{prompt}",
                "image_urls": ["{input_image_url}"],
                "num_images": 1,
                "aspect_ratio": "auto",
                "output_format": "png",
                "safety_tolerance": "4",
                "resolution": "1K",
                "limit_generations": True,
            },
        },
        "defaults": {
            "num_images": 1,
            "aspect_ratio": "auto",
            "output_format": "png",
            "safety_tolerance": "4",
            "resolution": "1K",
            "limit_generations": True,
        },
        "response": {
            "image_url_paths_priority": [["images", 0, "url"]],
        },
    },
    {
        "id": "fal:fal-ai/flux-2-pro/edit",
        "provider": "fal",
        "display_name": "FLUX.2 Pro Edit",
        "description": "FAL-hosted high-quality image edit model.",
        "api_key_env": "FAL_KEY",
        "request": {
            "model_path": "fal-ai/flux-2-pro/edit",
            "input_image_field": "image_urls",
            "arguments_template": {
                "prompt": "{prompt}",
                "image_urls": ["{input_image_url}"],
                "image_size": "auto",
                "enable_safety_checker": True,
                "safety_tolerance": "2",
                "output_format": "jpeg",
            },
        },
        "defaults": {
            "image_size": "auto",
            "enable_safety_checker": True,
            "safety_tolerance": "2",
            "output_format": "jpeg",
        },
        "response": {
            "image_url_paths_priority": [["images", 0, "url"]],
        },
    },
    {
        "id": "fal:fal-ai/flux-pro/kontext",
        "provider": "fal",
        "display_name": "FLUX.1 Kontext Pro",
        "description": "FAL-hosted FLUX.1 Kontext Pro model for targeted and scene-level image edits.",
        "api_key_env": "FAL_KEY",
        "request": {
            "model_path": "fal-ai/flux-pro/kontext",
            "arguments_template": {
                "prompt": "{prompt}",
                "image_url": "{input_image_url}",
            },
        },
        "defaults": {},
        "response": {
            "image_url_paths_priority": [["images", 0, "url"]],
        },
    },
    {
        "id": "fal:fal-ai/bytedance/seedream/v5/lite/edit",
        "provider": "fal",
        "display_name": "Seedream 5 Lite Edit",
        "description": "FAL-hosted ByteDance Seedream 5.0 Lite image editing model.",
        "api_key_env": "FAL_KEY",
        "request": {
            "model_path": "fal-ai/bytedance/seedream/v5/lite/edit",
            "arguments_template": {
                "prompt": "{prompt}",
                "image_urls": ["{input_image_url}"],
            },
        },
        "defaults": {},
        "response": {
            "image_url_paths_priority": [["images", 0, "url"]],
        },
    },
    {
        "id": "fal:ideogram/v4/image-to-image",
        "provider": "fal",
        "display_name": "Ideogram V4 Image-to-Image",
        "description": "FAL-hosted Ideogram V4 image-to-image model for structure-preserving edits.",
        "api_key_env": "FAL_KEY",
        "request": {
            "model_path": "ideogram/v4/image-to-image",
            "arguments_template": {
                "prompt": "{prompt}",
                "image_url": "{input_image_url}",
                "rendering_speed": "BALANCED",
            },
        },
        "defaults": {
            "rendering_speed": "BALANCED",
        },
        "response": {
            "image_url_paths_priority": [["images", 0, "url"]],
        },
    },
    {
        "id": "fal:xai/grok-imagine-image/edit",
        "provider": "fal",
        "display_name": "Grok Imagine Image Edit",
        "description": "FAL-hosted xAI Grok image editing model.",
        "api_key_env": "FAL_KEY",
        "request": {
            "model_path": "xai/grok-imagine-image/edit",
            "input_image_field": "image_urls",
            "arguments_template": {
                "prompt": "{prompt}",
                "image_urls": ["{input_image_url}"],
                "num_images": 1,
                "resolution": "1k",
                "output_format": "jpeg",
            },
        },
        "defaults": {
            "num_images": 1,
            "resolution": "1k",
            "output_format": "jpeg",
        },
        "response": {
            "image_url_paths_priority": [["images", 0, "url"]],
        },
    },
]
