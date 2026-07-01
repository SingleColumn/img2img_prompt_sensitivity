import { useEffect, useMemo, useState } from "react";
import {
  createPromptSet,
  deletePromptSet,
  deleteRun,
  generatePromptSet,
  getPromptSet,
  getRun,
  getRunJob,
  listInputImages,
  listModels,
  listPromptSets,
  listRuns,
  startRunJob,
  updatePromptSet,
} from "./api/client";
import type {
  InputImageChoice,
  ModelChoice,
  PromptGenerationMetadata,
  PromptSet,
  PromptSetSummary,
  PromptVariation,
  RunJob,
  RunIndex,
  RunSummary,
} from "./types/api";
import "./styles/app.css";

type BuilderMode = "existing" | "new";

const API_ORIGIN = "http://127.0.0.1:8000";

const EMPTY_PROMPT_SET: PromptSet = {
  prompt_set: "",
  baseline: {
    prompt: "",
    similarity_to_baseline: 1,
  },
  variations: [],
};

function buildEmptyDraft(): PromptSet {
  return JSON.parse(JSON.stringify(EMPTY_PROMPT_SET)) as PromptSet;
}

function normalizeVariationName(value: string): string {
  return value.trim().replace(/[_-]+/g, " ").replace(/\s+/g, " ").toLowerCase();
}

function isEquivalentVariationName(value: string): boolean {
  return normalizeVariationName(value) === "equivalent";
}

function promptKeyForVariation(variation: PromptVariation): string {
  return isEquivalentVariationName(variation.variation_name)
    ? "equivalent"
    : variation.variation_name;
}

function deriveGenerationOptions(promptSet: PromptSet) {
  const equivalent = promptSet.variations.find(
    (item) => isEquivalentVariationName(item.variation_name)
  );
  const nonEquivalentCount = promptSet.variations.filter(
    (item) => !isEquivalentVariationName(item.variation_name)
  ).length;

  return {
    includeEquivalent: Boolean(equivalent),
    variationCount: nonEquivalentCount,
  };
}

function formatSimilarity(value: number | null | undefined): string {
  if (typeof value !== "number") {
    return "pending";
  }
  return value.toFixed(4);
}

function formatSeconds(value: number | null | undefined): string {
  if (typeof value !== "number") {
    return "n/a";
  }
  return `${value.toFixed(2)}s`;
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "n/a";
  }
  return value;
}

function buildOutputImageUrl(runId: string, imagePath: string): string {
  return `${API_ORIGIN}/static/output-runs/${runId}/${imagePath}`;
}

function buildInputImageUrl(fileName: string): string {
  return `${API_ORIGIN}/static/input-images/${fileName}`;
}

function derivePromptSelection(promptSet: PromptSet): string[] {
  return ["baseline", ...promptSet.variations.map((variation) => promptKeyForVariation(variation))];
}

export default function App() {
  const [mode, setMode] = useState<BuilderMode>("existing");
  const [promptSets, setPromptSets] = useState<PromptSetSummary[]>([]);
  const [models, setModels] = useState<ModelChoice[]>([]);
  const [inputImages, setInputImages] = useState<InputImageChoice[]>([]);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [selectedPromptSetId, setSelectedPromptSetId] = useState("");
  const [selectedInputImage, setSelectedInputImage] = useState("");
  const [selectedModelIds, setSelectedModelIds] = useState<string[]>([]);
  const [selectedPromptKeys, setSelectedPromptKeys] = useState<string[]>(["baseline"]);
  const [selectedRunId, setSelectedRunId] = useState("");
  const [activeRunJob, setActiveRunJob] = useState<RunJob | null>(null);
  const [currentRun, setCurrentRun] = useState<RunIndex | null>(null);
  const [originalPromptSetId, setOriginalPromptSetId] = useState<string | null>(null);
  const [draft, setDraft] = useState<PromptSet>(buildEmptyDraft);
  const [includeEquivalent, setIncludeEquivalent] = useState(true);
  const [variationCount, setVariationCount] = useState(2);
  const [generationMetadata, setGenerationMetadata] =
    useState<PromptGenerationMetadata | null>(null);
  const [status, setStatus] = useState("Loading catalog...");
  const [error, setError] = useState("");
  const [busyAction, setBusyAction] = useState("");
  const [activeTab, setActiveTab] = useState<number>(0);
  const [promptsOpen, setPromptsOpen] = useState<boolean>(false);

  useEffect(() => {
    void refreshReferenceData();
  }, []);

  useEffect(() => {
    if (mode !== "existing") {
      return;
    }
    if (!selectedPromptSetId) {
      return;
    }
    void loadPromptSet(selectedPromptSetId);
  }, [mode, selectedPromptSetId]);

  useEffect(() => {
    if (!activeRunJob) {
      return;
    }
    if (activeRunJob.status === "completed" || activeRunJob.status === "failed") {
      return;
    }

    const intervalId = window.setInterval(() => {
      void getRunJob(activeRunJob.job_id)
        .then(async (job) => {
          setActiveRunJob(job);
          setStatus(job.message || `Run job ${job.status}.`);
          if (job.status === "completed" && job.run_id) {
            setSelectedRunId(job.run_id);
            const run = await getRun(job.run_id);
            setCurrentRun(run);
            const updatedRuns = await listRuns();
            setRuns(updatedRuns);
            setBusyAction("");
            setActiveRunJob(job);
            setActiveTab(2);
          }
          if (job.status === "failed") {
            setError(job.error || "Run failed.");
            setBusyAction("");
            setActiveRunJob(job);
          }
        })
        .catch((caught) => {
          setError(caught instanceof Error ? caught.message : "Unknown error");
          setBusyAction("");
          // Stop polling — the job is gone (e.g. server restarted) and will never appear.
          setActiveRunJob(null);
        });
    }, 1000);

    return () => window.clearInterval(intervalId);
  }, [activeRunJob]);

  async function refreshReferenceData(preferredPromptSetId?: string, preferredRunId?: string) {
    try {
      setError("");
      const [promptSetData, modelData, inputImageData, runData] = await Promise.all([
        listPromptSets(),
        listModels(),
        listInputImages(),
        listRuns(),
      ]);
      setPromptSets(promptSetData);
      setModels(modelData);
      setInputImages(inputImageData);
      setRuns(runData);

      const resolvedPromptSetId =
        preferredPromptSetId || selectedPromptSetId || promptSetData[0]?.prompt_set || "";

      if (!selectedInputImage && inputImageData[0]?.file_name) {
        setSelectedInputImage(inputImageData[0].file_name);
      }

      if (!selectedModelIds.length && modelData[0]?.id) {
        setSelectedModelIds([modelData[0].id]);
      }

      if (resolvedPromptSetId) {
        setSelectedPromptSetId(resolvedPromptSetId);
      } else {
        setStatus("No prompt sets saved yet. Start with a new one.");
      }

      const resolvedRunId = preferredRunId || selectedRunId || runData[0]?.run_id || "";
      if (resolvedRunId) {
        setSelectedRunId(resolvedRunId);
        await loadRun(resolvedRunId);
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unknown error");
      setStatus("Could not load reference data.");
    }
  }

  async function loadPromptSet(promptSetId: string) {
    try {
      setBusyAction("loading-prompt-set");
      setError("");
      const promptSet = await getPromptSet(promptSetId);
      setDraft(promptSet);
      setOriginalPromptSetId(promptSet.prompt_set);
      setSelectedPromptKeys(derivePromptSelection(promptSet));
      const options = deriveGenerationOptions(promptSet);
      setIncludeEquivalent(options.includeEquivalent);
      setVariationCount(options.variationCount);
      setMode("existing");
      setGenerationMetadata(null);
      setStatus(`Loaded prompt set ${promptSet.prompt_set}.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unknown error");
      setStatus("Could not load prompt set.");
    } finally {
      setBusyAction("");
    }
  }

  async function loadRun(runId: string) {
    try {
      setBusyAction("loading-run");
      setError("");
      const run = await getRun(runId);
      setCurrentRun(run);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unknown error");
    } finally {
      setBusyAction("");
    }
  }

  function handleCreateNew() {
    setMode("new");
    setSelectedPromptSetId("");
    setOriginalPromptSetId(null);
    setDraft(buildEmptyDraft());
    setSelectedPromptKeys(["baseline"]);
    setIncludeEquivalent(true);
    setVariationCount(2);
    setGenerationMetadata(null);
    setError("");
    setStatus("Drafting a new prompt set.");
    setActiveTab(1);
  }

  function handleVariationChange(index: number, nextVariation: PromptVariation) {
    setDraft((current) => {
      const variations = current.variations.slice();
      variations[index] = nextVariation;
      return {
        ...current,
        variations,
      };
    });
  }

  async function handleGenerate() {
    try {
      setBusyAction("generate");
      setError("");
      const response = await generatePromptSet({
        prompt_set: draft.prompt_set,
        baseline_prompt: draft.baseline.prompt,
        include_equivalent: includeEquivalent,
        variation_count: variationCount,
      });
      setDraft(response.prompt_set);
      setSelectedPromptKeys(derivePromptSelection(response.prompt_set));
      setGenerationMetadata(response.generation_metadata);
      setStatus("Generated equivalent and variation prompts.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unknown error");
      setStatus("Prompt generation failed.");
    } finally {
      setBusyAction("");
    }
  }

  async function handleSave() {
    try {
      setBusyAction("save");
      setError("");
      const payload = {
        prompt_set: draft.prompt_set,
        baseline: draft.baseline,
        variations: draft.variations,
      };
      const saved = originalPromptSetId
        ? await updatePromptSet(originalPromptSetId, payload)
        : await createPromptSet(payload);

      setDraft(saved);
      setOriginalPromptSetId(saved.prompt_set);
      setSelectedPromptSetId(saved.prompt_set);
      setMode("existing");
      setActiveTab(0);
      await refreshReferenceData(saved.prompt_set, selectedRunId);
      setStatus(`Saved prompt set ${saved.prompt_set}.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unknown error");
      setStatus("Save failed.");
    } finally {
      setBusyAction("");
    }
  }

  async function handleDeletePromptSet() {
    const promptSetId = originalPromptSetId || selectedPromptSetId || draft.prompt_set;
    if (!promptSetId) {
      setError("Select a prompt set to delete.");
      return;
    }
    if (!window.confirm(`Delete prompt set "${promptSetId}"?`)) {
      return;
    }

    try {
      setBusyAction("delete-prompt-set");
      setError("");
      await deletePromptSet(promptSetId);

      const remainingPromptSets = promptSets.filter((item) => item.prompt_set !== promptSetId);
      const nextPromptSetId = remainingPromptSets[0]?.prompt_set || "";

      setPromptSets(remainingPromptSets);
      setSelectedPromptSetId(nextPromptSetId);
      setOriginalPromptSetId(null);
      setDraft(buildEmptyDraft());
      setSelectedPromptKeys(["baseline"]);
      setIncludeEquivalent(true);
      setVariationCount(2);
      setGenerationMetadata(null);
      setMode(nextPromptSetId ? "existing" : "new");

      if (nextPromptSetId) {
        await loadPromptSet(nextPromptSetId);
        setStatus(`Deleted prompt set ${promptSetId}.`);
      } else {
        setStatus("Deleted prompt set. No prompt sets saved yet.");
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unknown error");
      setStatus("Delete failed.");
    } finally {
      setBusyAction("");
    }
  }

  async function handleCreateRun() {
    const availablePromptKeys = new Set(selectablePrompts.map((item) => item.key));
    const effectivePromptKeys = selectedPromptKeys.filter((key) => availablePromptKeys.has(key));

    if (!draft.prompt_set) {
      setError("Select or save a prompt set before running an experiment.");
      return;
    }
    if (!selectedInputImage) {
      setError("Select an input image.");
      return;
    }
    if (!selectedModelIds.length) {
      setError("Select at least one model.");
      return;
    }
    if (!effectivePromptKeys.length) {
      setError("Select at least one prompt for the run.");
      return;
    }
    if (
      selectedModelIds.some(
        (modelId) =>
          ![
            "openai:gpt-image-2:edit",
            "fal:fal-ai/nano-banana-2/edit",
            "fal:fal-ai/flux-2-pro/edit",
            "fal:fal-ai/flux-pro/kontext",
            "fal:fal-ai/bytedance/seedream/v5/lite/edit",
            "fal:ideogram/v4/image-to-image",
            "fal:xai/grok-imagine-image/edit",
          ].includes(modelId)
      )
    ) {
      setError(
        "Real provider execution currently supports GPT Image 2 Edit, Nano Banana 2 Edit, FLUX.2 Pro Edit, FLUX.1 Kontext Pro, Seedream 5 Lite Edit, Ideogram V4 Image-to-Image, and Grok Imagine Image Edit."
      );
      return;
    }

    try {
      setBusyAction("create-run");
      setError("");
      const job = await startRunJob({
        prompt_set_id: draft.prompt_set,
        input_image: selectedInputImage,
        model_ids: selectedModelIds,
        prompt_keys: effectivePromptKeys,
        execution_mode: "provider",
      });
      setActiveRunJob(job);
      setStatus(job.message || "Run queued.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unknown error");
      setStatus("Run creation failed.");
      setBusyAction("");
    }
  }

  async function handleDeleteRun() {
    if (!selectedRunId) {
      setError("Select a run to delete.");
      return;
    }
    if (!window.confirm(`Delete run "${selectedRunId}"?`)) {
      return;
    }

    try {
      setBusyAction("delete-run");
      setError("");
      await deleteRun(selectedRunId);

      const remainingRuns = runs.filter((run) => run.run_id !== selectedRunId);
      const nextRunId = remainingRuns[0]?.run_id || "";

      setRuns(remainingRuns);
      setSelectedRunId(nextRunId);

      if (currentRun?.run_id === selectedRunId) {
        setCurrentRun(null);
      }

      if (nextRunId) {
        await loadRun(nextRunId);
        setStatus(`Deleted run ${selectedRunId}.`);
      } else {
        setCurrentRun(null);
        setStatus("Deleted run. No past runs remain.");
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unknown error");
      setStatus("Run delete failed.");
    } finally {
      setBusyAction("");
    }
  }

  const orderedVariations = useMemo(() => {
    const equivalent = draft.variations.find((item) =>
      isEquivalentVariationName(item.variation_name)
    );
    const others = draft.variations.filter(
      (item) => !isEquivalentVariationName(item.variation_name)
    );
    return equivalent ? [equivalent, ...others] : others;
  }, [draft.variations]);

  const selectablePrompts = useMemo(
    () => [
      {
        key: "baseline",
        label: "Baseline",
        prompt: draft.baseline.prompt,
      },
      ...orderedVariations.map((variation) => ({
        key: promptKeyForVariation(variation),
        label: isEquivalentVariationName(variation.variation_name)
          ? "Equivalent"
          : variation.variation_name,
        prompt: variation.prompt,
      })),
    ],
    [draft.baseline.prompt, orderedVariations]
  );

  const runItemsByModel = useMemo(() => {
    const grouped = new Map<string, RunIndex["items"]>();
    if (!currentRun) {
      return grouped;
    }
    for (const item of currentRun.items) {
      const existing = grouped.get(item.model_id) ?? [];
      existing.push(item);
      grouped.set(item.model_id, existing);
    }
    return grouped;
  }, [currentRun]);

  const activeRunProgress =
    activeRunJob && activeRunJob.total_steps
      ? Math.round((activeRunJob.completed_steps / activeRunJob.total_steps) * 100)
      : 0;

  function resultColumnCount(promptCount: number): string {
    return `repeat(${1 + promptCount}, minmax(0, 1fr))`;
  }

  return (
    <main className="app-shell">
      <section className="hero">
        <p className="eyebrow">Local Prompt Sensitivity Lab</p>
        <h1>img2img lab</h1>
        <p className="lede">
          Run a prompt set against one or more image models and compare outputs
          side by side to see how prompt wording affects the result.
        </p>
      </section>

      <nav>
        <div className="tab-bar" role="tablist">
          {(["Prompt sets", "New set", "Run & results", "Past runs"] as const).map(
            (label, i) => (
              <button
                key={label}
                role="tab"
                type="button"
                className={activeTab === i ? "tab-button active" : "tab-button"}
                aria-selected={activeTab === i}
                onClick={() => setActiveTab(i)}
              >
                {label}
              </button>
            )
          )}
        </div>
      </nav>

      {error ? <p className="error-banner">{error}</p> : null}
      <p className="status-line">{status}</p>

      {activeRunJob &&
      activeRunJob.status !== "completed" &&
      activeRunJob.status !== "failed" ? (
        <section className="panel progress-panel">
          <div className="section-heading">
            <div>
              <p className="section-kicker">Run Progress</p>
              <h2>{activeRunJob.status}</h2>
            </div>
            <strong>
              {activeRunJob.completed_steps}/{activeRunJob.total_steps || "?"}
            </strong>
          </div>
          <div className="progress-bar-track">
            <div className="progress-bar-fill" style={{ width: `${activeRunProgress}%` }} />
          </div>
          <p className="helper-copy">{activeRunJob.message}</p>
          <p className="helper-copy">
            Model: {activeRunJob.current_model_id || "waiting"} | Prompt:{" "}
            {activeRunJob.current_prompt_key || "waiting"}
          </p>
          <p className="helper-copy">
            Last update: {formatDateTime(activeRunJob.last_updated_at)} | Step started:{" "}
            {formatDateTime(activeRunJob.step_started_at)} | Stall threshold:{" "}
            {activeRunJob.stall_timeout_s != null ? `${activeRunJob.stall_timeout_s}s` : "n/a"}
          </p>
          {activeRunJob.error ? <p className="error-banner">{activeRunJob.error}</p> : null}
        </section>
      ) : null}

      {activeTab === 0 ? (
        <div className="tab-content">
          <section className="panel">
            <div className="section-heading">
              <div>
                <p className="section-kicker">Library</p>
                <h2>Prompt sets</h2>
              </div>
              <button type="button" className="ghost-button" onClick={handleCreateNew}>
                New set
              </button>
            </div>

            <div className="set-selector">
              <select
                value={selectedPromptSetId}
                onChange={(e) => {
                  setMode("existing");
                  setSelectedPromptSetId(e.target.value);
                }}
                disabled={!promptSets.length || busyAction === "loading-prompt-set"}
              >
                {promptSets.length ? null : <option value="">No saved prompt sets</option>}
                {promptSets.map((item) => (
                  <option key={item.prompt_set} value={item.prompt_set}>
                    {item.prompt_set} - {item.variation_count} variation
                    {item.variation_count !== 1 ? "s" : ""}
                    {item.has_equivalent ? ", including equivalent" : ""}
                  </option>
                ))}
              </select>
            </div>
          </section>

          {draft.prompt_set ? (
            <section className="panel">
              <div className="section-heading">
                <div>
                  <p className="section-kicker">Prompt Review</p>
                  <h2>{draft.prompt_set}</h2>
                </div>
                <div className="action-row">
                  <button
                    type="button"
                    className="primary-button"
                    onClick={() => void handleSave()}
                    disabled={busyAction !== ""}
                  >
                    {busyAction === "save" ? "Saving..." : "Save prompt set"}
                  </button>
                  <button
                    type="button"
                    className="ghost-button"
                    onClick={() => void handleDeletePromptSet()}
                    disabled={busyAction !== "" || !draft.prompt_set}
                  >
                    {busyAction === "delete-prompt-set" ? "Deleting..." : "Delete set"}
                  </button>
                </div>
              </div>

              <div className="prompt-card-grid">
                <article className="prompt-card">
                  <div className="prompt-card-header">
                    <div>
                      <h3>Baseline</h3>
                    </div>
                    <span className="similarity-pill">similarity -</span>
                  </div>
                  <label className="field">
                    <span className="field-label">Variation name</span>
                    <input value="Baseline" disabled />
                  </label>
                  <label className="field">
                    <span className="field-label">Variation type</span>
                    <input value="baseline" disabled />
                  </label>
                  <label className="field field-block field-grow">
                    <span className="field-label">Prompt</span>
                    <textarea
                      value={draft.baseline.prompt}
                      onChange={(e) =>
                        setDraft((cur) => ({
                          ...cur,
                          baseline: { ...cur.baseline, prompt: e.target.value },
                        }))
                      }
                    />
                  </label>
                </article>

                {orderedVariations.map((variation, index) => (
                  <article key={`${variation.variation_name}-${index}`} className="prompt-card">
                    <div className="prompt-card-header">
                      <div>
                        <h3>{variation.variation_name}</h3>
                      </div>
                      <span className="similarity-pill">
                        similarity {formatSimilarity(variation.similarity_to_baseline)}
                      </span>
                    </div>

                    <label className="field">
                      <span className="field-label">Variation name</span>
                      <input
                        value={variation.variation_name}
                        onChange={(e) =>
                          handleVariationChange(index, {
                            ...variation,
                            variation_name: e.target.value,
                          })
                        }
                      />
                    </label>

                    <label className="field">
                      <span className="field-label">Variation type</span>
                      <input
                        value={variation.variation_type}
                        onChange={(e) =>
                          handleVariationChange(index, {
                            ...variation,
                            variation_type: e.target.value,
                          })
                        }
                      />
                    </label>

                    <label className="field field-block field-grow">
                      <span className="field-label">Prompt</span>
                      <textarea
                        value={variation.prompt}
                        onChange={(e) =>
                          handleVariationChange(index, {
                            ...variation,
                            prompt: e.target.value,
                          })
                        }
                      />
                    </label>
                  </article>
                ))}
              </div>
            </section>
          ) : null}
        </div>
      ) : null}

      {activeTab === 1 ? (
        <div className="tab-content">
          <section className="panel">
            <div className="section-heading">
              <div>
                <p className="section-kicker">Prompt Builder</p>
                <h2>{originalPromptSetId ? "Edit saved prompt set" : "Create prompt set"}</h2>
              </div>
              <div className="action-row">
                <button
                  type="button"
                  className="primary-button"
                  onClick={() => void handleGenerate()}
                  disabled={busyAction !== ""}
                >
                  {busyAction === "generate" ? "Generating..." : "Generate prompts"}
                </button>
                <button
                  type="button"
                  className="primary-button"
                  onClick={() => void handleSave()}
                  disabled={busyAction !== ""}
                >
                  {busyAction === "save" ? "Saving..." : "Save prompt set"}
                </button>
              </div>
            </div>

            <div className="form-grid">
              <label className="field">
                <span className="field-label">Prompt set name</span>
                <input
                  value={draft.prompt_set}
                  onChange={(e) => setDraft((cur) => ({ ...cur, prompt_set: e.target.value }))}
                  placeholder="Identity Pixel Art"
                />
              </label>

              <label className="field checkbox-field">
                <input
                  type="checkbox"
                  checked={includeEquivalent}
                  onChange={(e) => setIncludeEquivalent(e.target.checked)}
                />
                <span>Generate equivalent</span>
              </label>

              <label className="field">
                <span className="field-label">Variation count</span>
                <input
                  type="number"
                  min={0}
                  max={10}
                  value={variationCount}
                  onChange={(e) => setVariationCount(Number(e.target.value))}
                />
              </label>
            </div>

            <label className="field field-block">
              <span className="field-label">Baseline prompt</span>
              <textarea
                value={draft.baseline.prompt}
                onChange={(e) =>
                  setDraft((cur) => ({
                    ...cur,
                    baseline: { ...cur.baseline, prompt: e.target.value },
                  }))
                }
                rows={6}
                placeholder="Write the baseline image-edit prompt here."
              />
            </label>

            {generationMetadata ? (
              <div className="similarity-banner">
                <div>
                  <span className="metric-label">Generated with</span>
                  <strong>{generationMetadata.llm_model}</strong>
                </div>
              </div>
            ) : null}
          </section>

          {orderedVariations.length > 0 ? (
            <section className="panel">
              <div className="section-heading">
                <div>
                  <p className="section-kicker">Prompt Review</p>
                  <h2>Equivalent and variations</h2>
                </div>
              </div>

              <div className="prompt-card-grid">
                {orderedVariations.map((variation, index) => (
                  <article key={`${variation.variation_name}-${index}`} className="prompt-card">
                    <div className="prompt-card-header">
                      <div>
                        <h3>{variation.variation_name}</h3>
                      </div>
                      <span className="similarity-pill">
                        similarity {formatSimilarity(variation.similarity_to_baseline)}
                      </span>
                    </div>

                    <label className="field">
                      <span className="field-label">Variation name</span>
                      <input
                        value={variation.variation_name}
                        onChange={(e) =>
                          handleVariationChange(index, {
                            ...variation,
                            variation_name: e.target.value,
                          })
                        }
                      />
                    </label>

                    <label className="field">
                      <span className="field-label">Variation type</span>
                      <input
                        value={variation.variation_type}
                        onChange={(e) =>
                          handleVariationChange(index, {
                            ...variation,
                            variation_type: e.target.value,
                          })
                        }
                      />
                    </label>

                    <label className="field field-block field-grow">
                      <span className="field-label">Prompt</span>
                      <textarea
                        value={variation.prompt}
                        onChange={(e) =>
                          handleVariationChange(index, {
                            ...variation,
                            prompt: e.target.value,
                          })
                        }
                      />
                    </label>
                  </article>
                ))}
              </div>
            </section>
          ) : (
            <section className="panel">
              <article className="prompt-card prompt-card-empty">
                <h3>No generated prompts yet</h3>
                <p>
                  Write a baseline prompt, choose whether you want an equivalent
                  and how many variations to create, then click Generate prompts.
                </p>
              </article>
            </section>
          )}
        </div>
      ) : null}

      {activeTab === 2 ? (
        <div className="tab-content">
          <section className="panel">
            <div className="section-heading">
              <div>
                <p className="section-kicker">Experiment Setup</p>
                <h2>Run configuration</h2>
              </div>
              <button
                type="button"
                className="primary-button"
                onClick={() => void handleCreateRun()}
                disabled={busyAction !== ""}
              >
                {busyAction === "create-run" ? "Running..." : "Run experiment"}
              </button>
            </div>

            <div className="runtime-grid">
              <label className="field">
                <span className="field-label">Prompt set</span>
                <select
                  value={selectedPromptSetId}
                  onChange={(e) => {
                    setMode("existing");
                    setSelectedPromptSetId(e.target.value);
                  }}
                  disabled={!promptSets.length || busyAction === "loading-prompt-set"}
                >
                  {promptSets.length ? null : <option value="">No saved prompt sets</option>}
                  {promptSets.map((item) => (
                    <option key={item.prompt_set} value={item.prompt_set}>
                      {item.prompt_set}
                    </option>
                  ))}
                </select>
              </label>

              <div className="field">
                <span className="field-label">Input image</span>
                <select
                  value={selectedInputImage}
                  onChange={(e) => setSelectedInputImage(e.target.value)}
                >
                  {inputImages.map((item) => (
                    <option key={item.file_name} value={item.file_name}>
                      {item.file_name}
                    </option>
                  ))}
                </select>
                {selectedInputImage ? (
                  <img
                    className="input-image-thumb"
                    src={buildInputImageUrl(selectedInputImage)}
                    alt={selectedInputImage}
                  />
                ) : null}
              </div>

              <div className="field">
                <span className="field-label">Models</span>
                <div className="checkbox-list">
                  {models.map((item) => (
                    <label key={item.id} className="checkbox-item">
                      <input
                        type="checkbox"
                        checked={selectedModelIds.includes(item.id)}
                        onChange={(e) => {
                          setSelectedModelIds((cur) =>
                            e.target.checked
                              ? [...cur, item.id]
                              : cur.filter((modelId) => modelId !== item.id)
                          );
                        }}
                      />
                      <span>{item.display_name}</span>
                    </label>
                  ))}
                </div>
              </div>
            </div>

            <div className="field field-block">
              <div className="selection-toolbar">
                <span className="field-label">Prompts to run</span>
                <div className="selection-actions">
                  <button
                    type="button"
                    className="ghost-button"
                    onClick={() => setSelectedPromptKeys(selectablePrompts.map((item) => item.key))}
                  >
                    Select all
                  </button>
                  <button
                    type="button"
                    className="ghost-button"
                    onClick={() => setSelectedPromptKeys(["baseline"])}
                  >
                    Baseline only
                  </button>
                </div>
              </div>

              <div className="variation-select-grid">
                {selectablePrompts.map((item) => (
                  <label
                    key={item.key}
                    className={
                      selectedPromptKeys.includes(item.key)
                        ? "variation-select-card selected"
                        : "variation-select-card"
                    }
                  >
                    <input
                      type="checkbox"
                      checked={selectedPromptKeys.includes(item.key)}
                      onChange={(e) => {
                        setSelectedPromptKeys((cur) =>
                          e.target.checked
                            ? [...new Set([...cur, item.key])]
                            : cur.filter((k) => k !== item.key)
                        );
                      }}
                    />
                    <span>
                      <span className="vsc-name">{item.label}</span>
                      <span className="vsc-excerpt">{item.prompt}</span>
                    </span>
                  </label>
                ))}
              </div>

              <div className="accordion">
                <button
                  type="button"
                  className="accordion-trigger"
                  onClick={() => setPromptsOpen((o) => !o)}
                  aria-expanded={promptsOpen}
                >
                  <span>Prompt text ({selectedPromptKeys.length} selected)</span>
                  <i
                    className={promptsOpen ? "accordion-chevron open" : "accordion-chevron"}
                    aria-hidden="true"
                  >
                    v
                  </i>
                </button>
                <div className={promptsOpen ? "accordion-body open" : "accordion-body"}>
                  {selectablePrompts
                    .filter((p) => selectedPromptKeys.includes(p.key))
                    .map((p) => (
                      <div key={p.key} className="accordion-prompt-item">
                        <span className="accordion-prompt-label">{p.label}</span>
                        <p className="accordion-prompt-text">{p.prompt}</p>
                      </div>
                    ))}
                </div>
              </div>
            </div>

            <p className="helper-copy">
              Real provider execution supports <strong>GPT Image 2 Edit</strong>,{" "}
              <strong>Nano Banana 2 Edit</strong>, <strong>FLUX.2 Pro Edit</strong>,{" "}
              <strong>FLUX.1 Kontext Pro</strong>, <strong>Seedream 5 Lite Edit</strong>,{" "}
              <strong>Ideogram V4 Image-to-Image</strong>, and{" "}
              <strong>Grok Imagine Image Edit</strong>.
            </p>
          </section>

          {currentRun ? (
            <section className="panel">
              <p className="section-kicker">Generation status</p>
              <h2>{currentRun.run_id}</h2>
              <div className="status-list">
                {currentRun.selected_models.flatMap((model) =>
                  currentRun.prompts.map((prompt) => {
                    const item = (runItemsByModel.get(model.id) ?? []).find(
                      (i) => i.prompt_key === prompt.key
                    );
                    return (
                      <div key={`${model.id}-${prompt.key}`} className="status-item">
                        <span className="status-item-label">
                          <span className="status-dot done" />
                          {prompt.label} · {model.display_name}
                        </span>
                        <span className="status-value done">
                          Done
                          {item?.generation_elapsed_s != null
                            ? ` · ${formatSeconds(item.generation_elapsed_s)}`
                            : ""}
                        </span>
                      </div>
                    );
                  })
                )}
              </div>
            </section>
          ) : null}

          {currentRun ? (
            <section className="panel">
              <div className="section-heading">
                <div>
                  <p className="section-kicker">Results</p>
                  <h2>{currentRun.run_id}</h2>
                </div>
              </div>

              <div className="run-meta-grid">
                <div>
                  <span className="metric-label">Prompt set</span>
                  <strong>{currentRun.prompt_set_id}</strong>
                </div>
                <div>
                  <span className="metric-label">Input image</span>
                  <strong>{currentRun.input_image}</strong>
                </div>
                <div>
                  <span className="metric-label">Generated at</span>
                  <strong>{currentRun.generated_at}</strong>
                </div>
              </div>

              <div className="results-stack">
                {currentRun.selected_models.map((model) => {
                  const modelItems = runItemsByModel.get(model.id) ?? [];
                  const itemsByPrompt = new Map(
                    modelItems.map((item) => [item.prompt_key, item])
                  );

                  return (
                    <div key={model.id} className="result-group">
                      <div className="result-group-header">
                        <h3 className="result-group-title">
                          {currentRun.prompt_set_id} · {model.display_name}
                        </h3>
                        <span className="result-group-meta">{currentRun.generated_at}</span>
                      </div>

                      <div
                        className="result-image-row"
                        style={{
                          gridTemplateColumns: resultColumnCount(currentRun.prompts.length),
                        }}
                      >
                        <div className="result-image-card input-card">
                          <div className="image-area">
                            <img
                              src={buildInputImageUrl(currentRun.input_image)}
                              alt={currentRun.input_image}
                            />
                          </div>
                          <div className="image-meta">
                            <strong>Input image</strong>
                            <span className="source-label">{currentRun.input_image}</span>
                          </div>
                        </div>

                        {currentRun.prompts.map((prompt) => {
                          const item = itemsByPrompt.get(prompt.key);
                          return (
                            <div key={prompt.key} className="result-image-card">
                              {item ? (
                                <div className="image-area">
                                  <img
                                    src={buildOutputImageUrl(currentRun.run_id, item.image_path)}
                                    alt={`${model.display_name} - ${prompt.label}`}
                                  />
                                </div>
                              ) : (
                                <div className="image-area pending">Pending</div>
                              )}
                              <div className="image-meta">
                                <strong>{prompt.label}</strong>
                                <span>
                                  similarity {formatSimilarity(prompt.similarity_to_baseline)}
                                </span>
                                {item?.generation_elapsed_s != null ? (
                                  <span className="timing">
                                    total {formatSeconds(item.generation_elapsed_s)} | provider{" "}
                                    {formatSeconds(item.provider_elapsed_s)} | download{" "}
                                    {formatSeconds(item.download_elapsed_s)}
                                  </span>
                                ) : null}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>
          ) : null}
        </div>
      ) : null}

      {activeTab === 3 ? (
        <div className="tab-content">
          <div className="past-runs-layout">
            <aside className="panel">
              <div className="section-heading">
                <div>
                  <p className="section-kicker">Run history</p>
                  <h2>Past runs</h2>
                </div>
                <button
                  type="button"
                  className="ghost-button"
                  onClick={() => void handleDeleteRun()}
                  disabled={busyAction !== "" || !selectedRunId}
                >
                  {busyAction === "delete-run" ? "Deleting..." : "Delete run"}
                </button>
              </div>
              <ul className="run-list" style={{ marginTop: 14 }}>
                {runs.map((run) => (
                  <li key={run.run_id}>
                    <button
                      type="button"
                      title={run.run_id}
                      className={
                        run.run_id === selectedRunId ? "run-list-item active" : "run-list-item"
                      }
                      onClick={() => {
                        setSelectedRunId(run.run_id);
                        void loadRun(run.run_id);
                      }}
                    >
                      <span className="run-id">{run.run_id}</span>
                      <span className="run-meta">
                        {run.prompt_set_id} · {run.model_count} model
                        {run.model_count !== 1 ? "s" : ""} · {run.prompt_count} prompt
                        {run.prompt_count !== 1 ? "s" : ""}
                        {run.avg_generation_elapsed_s != null
                          ? ` · avg ${formatSeconds(run.avg_generation_elapsed_s)}`
                          : ""}
                      </span>
                    </button>
                  </li>
                ))}
                {runs.length === 0 ? (
                  <li>
                    <p className="helper-copy">No runs yet.</p>
                  </li>
                ) : null}
              </ul>
            </aside>

            <div>
              {currentRun ? (
                <section className="panel">
                  <div className="section-heading">
                    <div>
                      <p className="section-kicker">Results</p>
                      <h2>{currentRun.run_id}</h2>
                    </div>
                  </div>

                  <div className="run-meta-grid">
                    <div>
                      <span className="metric-label">Prompt set</span>
                      <strong>{currentRun.prompt_set_id}</strong>
                    </div>
                    <div>
                      <span className="metric-label">Input image</span>
                      <strong>{currentRun.input_image}</strong>
                    </div>
                    <div>
                      <span className="metric-label">Generated at</span>
                      <strong>{currentRun.generated_at}</strong>
                    </div>
                    <div>
                      <span className="metric-label">Mode</span>
                      <strong>{currentRun.execution_mode}</strong>
                    </div>
                  </div>

                  <div className="results-stack">
                    {currentRun.selected_models.map((model) => {
                      const modelItems = runItemsByModel.get(model.id) ?? [];
                      const itemsByPrompt = new Map(
                        modelItems.map((item) => [item.prompt_key, item])
                      );

                      return (
                        <div key={model.id} className="result-group">
                          <div className="result-group-header">
                            <h3 className="result-group-title">
                              {currentRun.prompt_set_id} · {model.display_name}
                            </h3>
                            <span className="result-group-meta">{currentRun.generated_at}</span>
                          </div>

                          <div
                            className="result-image-row"
                            style={{
                              gridTemplateColumns: resultColumnCount(currentRun.prompts.length),
                            }}
                          >
                            <div className="result-image-card input-card">
                              <div className="image-area">
                                <img
                                  src={buildInputImageUrl(currentRun.input_image)}
                                  alt={currentRun.input_image}
                                />
                              </div>
                              <div className="image-meta">
                                <strong>Input image</strong>
                                <span className="source-label">{currentRun.input_image}</span>
                              </div>
                            </div>

                            {currentRun.prompts.map((prompt) => {
                              const item = itemsByPrompt.get(prompt.key);
                              return (
                                <div key={prompt.key} className="result-image-card">
                                  {item ? (
                                    <div className="image-area">
                                      <img
                                        src={buildOutputImageUrl(currentRun.run_id, item.image_path)}
                                        alt={`${model.display_name} - ${prompt.label}`}
                                      />
                                    </div>
                                  ) : (
                                    <div className="image-area pending">Missing</div>
                                  )}
                                  <div className="image-meta">
                                    <strong>{prompt.label}</strong>
                                    <span>
                                      similarity{" "}
                                      {formatSimilarity(prompt.similarity_to_baseline)}
                                    </span>
                                    {item?.generation_elapsed_s != null ? (
                                      <span className="timing">
                                        total {formatSeconds(item.generation_elapsed_s)} | provider{" "}
                                        {formatSeconds(item.provider_elapsed_s)} | download{" "}
                                        {formatSeconds(item.download_elapsed_s)}
                                      </span>
                                    ) : null}
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </section>
              ) : (
                <section className="panel">
                  <p className="helper-copy">Select a run from the list to view its results.</p>
                </section>
              )}
            </div>
          </div>
        </div>
      ) : null}
    </main>
  );
}
