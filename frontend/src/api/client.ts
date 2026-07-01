import type {
  InputImageChoice,
  ModelChoice,
  PromptGenerationRequest,
  PromptGenerationResponse,
  PromptSet,
  PromptSetSummary,
  PromptSetUpsertRequest,
  RunCreateRequest,
  RunIndex,
  RunJob,
  RunSummary,
} from "../types/api";

const API_BASE = "http://127.0.0.1:8000/api";

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });
  if (!response.ok) {
    let detail = `Request failed: ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) {
        detail = payload.detail;
      }
    } catch {
      // Ignore non-JSON errors and keep the fallback message.
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

async function fetchEmpty(path: string, init?: RequestInit): Promise<void> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });
  if (!response.ok) {
    let detail = `Request failed: ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) {
        detail = payload.detail;
      }
    } catch {
      // Ignore non-JSON errors and keep the fallback message.
    }
    throw new Error(detail);
  }
}

export function listPromptSets(): Promise<PromptSetSummary[]> {
  return fetchJson<PromptSetSummary[]>("/prompt-sets");
}

export function getPromptSet(promptSetId: string): Promise<PromptSet> {
  return fetchJson<PromptSet>(`/prompt-sets/${encodeURIComponent(promptSetId)}`);
}

export function generatePromptSet(
  request: PromptGenerationRequest
): Promise<PromptGenerationResponse> {
  return fetchJson<PromptGenerationResponse>("/prompt-sets/generate", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export function createPromptSet(request: PromptSetUpsertRequest): Promise<PromptSet> {
  return fetchJson<PromptSet>("/prompt-sets", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export function updatePromptSet(
  originalPromptSetId: string,
  request: PromptSetUpsertRequest
): Promise<PromptSet> {
  return fetchJson<PromptSet>(`/prompt-sets/${encodeURIComponent(originalPromptSetId)}`, {
    method: "PUT",
    body: JSON.stringify(request),
  });
}

export function deletePromptSet(promptSetId: string): Promise<void> {
  return fetchEmpty(`/prompt-sets/${encodeURIComponent(promptSetId)}`, {
    method: "DELETE",
  });
}

export function recomputeSimilarity(promptSetId: string): Promise<PromptSet> {
  return fetchJson<PromptSet>(
    `/prompt-sets/${encodeURIComponent(promptSetId)}/recompute-similarity`,
    {
      method: "POST",
    }
  );
}

export function listModels(): Promise<ModelChoice[]> {
  return fetchJson<ModelChoice[]>("/models");
}

export function listInputImages(): Promise<InputImageChoice[]> {
  return fetchJson<InputImageChoice[]>("/input-images");
}

export function createRun(request: RunCreateRequest): Promise<RunIndex> {
  return fetchJson<RunIndex>("/runs", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export function listRuns(): Promise<RunSummary[]> {
  return fetchJson<RunSummary[]>("/runs");
}

export function getRun(runId: string): Promise<RunIndex> {
  return fetchJson<RunIndex>(`/runs/${encodeURIComponent(runId)}`);
}

export function deleteRun(runId: string): Promise<void> {
  return fetchEmpty(`/runs/${encodeURIComponent(runId)}`, {
    method: "DELETE",
  });
}

export function startRunJob(request: RunCreateRequest): Promise<RunJob> {
  return fetchJson<RunJob>("/runs/jobs", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export function getRunJob(jobId: string): Promise<RunJob> {
  return fetchJson<RunJob>(`/runs/jobs/${encodeURIComponent(jobId)}`);
}
