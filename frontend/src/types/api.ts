export type PromptSetSummary = {
  prompt_set: string;
  baseline_prompt: string;
  variation_count: number;
  has_equivalent: boolean;
};

export type BaselinePrompt = {
  prompt: string;
  similarity_to_baseline: number;
};

export type PromptVariation = {
  variation_name: string;
  variation_type: string;
  prompt: string;
  similarity_to_baseline: number | null;
};

export type PromptSet = {
  prompt_set: string;
  baseline: BaselinePrompt;
  variations: PromptVariation[];
};

export type PromptGenerationMetadata = {
  llm_provider: "openai";
  llm_model: string;
  template_version: string;
};

export type PromptGenerationResponse = {
  prompt_set: PromptSet;
  generation_metadata: PromptGenerationMetadata;
};

export type PromptGenerationRequest = {
  prompt_set: string;
  baseline_prompt: string;
  include_equivalent: boolean;
  variation_count: number;
};

export type PromptSetUpsertRequest = {
  prompt_set: string;
  baseline: BaselinePrompt;
  variations: PromptVariation[];
};

export type ModelChoice = {
  id: string;
  provider: string;
  display_name: string;
  description: string;
};

export type InputImageChoice = {
  file_name: string;
  url: string;
};

export type RunCreateRequest = {
  prompt_set_id: string;
  input_image: string;
  model_ids: string[];
  prompt_keys: string[];
  execution_mode: "mock" | "provider";
};

export type RunModelInfo = {
  id: string;
  display_name: string;
};

export type RunPromptInfo = {
  key: string;
  label: string;
  prompt: string;
  prompt_kind: string;
  variation_type?: string | null;
  similarity_to_baseline?: number | null;
};

export type RunItem = {
  model_id: string;
  model_display_name: string;
  prompt_key: string;
  prompt_label: string;
  prompt_kind: string;
  variation_type?: string | null;
  similarity_to_baseline?: number | null;
  prompt_text: string;
  output_file: string;
  image_path: string;
  timestamp: string;
  generation_elapsed_s?: number | null;
  provider_elapsed_s?: number | null;
  download_elapsed_s?: number | null;
};

export type RunIndex = {
  run_id: string;
  generated_at: string;
  prompt_set_id: string;
  input_image: string;
  execution_mode: string;
  selected_models: RunModelInfo[];
  prompts: RunPromptInfo[];
  items: RunItem[];
};

export type RunSummary = {
  run_id: string;
  generated_at: string;
  prompt_set_id: string;
  input_image: string;
  execution_mode: string;
  model_count: number;
  prompt_count: number;
  avg_generation_elapsed_s?: number | null;
};

export type RunJob = {
  job_id: string;
  status: "queued" | "running" | "stalled" | "completed" | "failed";
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  last_updated_at?: string | null;
  step_started_at?: string | null;
  stall_timeout_s?: number | null;
  execution_mode: string;
  prompt_set_id: string;
  input_image: string;
  model_ids: string[];
  prompt_keys: string[];
  completed_steps: number;
  total_steps: number;
  current_model_id?: string | null;
  current_prompt_key?: string | null;
  message: string;
  run_id?: string | null;
  error?: string | null;
};
