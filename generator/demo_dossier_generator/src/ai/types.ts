/**
 * The model is swappable. Every provider implements the same small interface:
 * send a prompt, get text back (streamed when the provider supports it).
 *
 *  - claude:    the hosted demo on claude.ai. Runs on the Claude account of
 *               whoever is using the page; no key needed. Only works inside
 *               the published Claude page.
 *  - anthropic: Anthropic API with your own key (local version).
 *  - openai:    any OpenAI-compatible endpoint: OpenAI, Gemini, Groq,
 *               OpenRouter, or a free local model in Ollama / LM Studio.
 *  - offline:   no model at all; the built-in sample generator.
 */

export type ProviderId = "claude" | "anthropic" | "openai" | "offline";

export interface ModelSettings {
  provider: ProviderId;
  claude: { tier: "quick" | "default" | "complex" };
  anthropic: { apiKey: string; model: string };
  openai: { preset: string; baseUrl: string; apiKey: string; model: string };
  /** Keep API keys in this browser's storage between visits. Off by default. */
  rememberKeys: boolean;
}

export interface CompletionRequest {
  system: string;
  prompt: string;
  signal?: AbortSignal;
  /** Called with the whole answer so far, as it streams in. */
  onText?: (textSoFar: string) => void;
  /** Rough size of the answer, used for max_tokens. */
  maxTokens?: number;
}

export interface ModelProvider {
  id: ProviderId;
  /** Short name for the UI: "Claude (your account)". */
  label: string;
  /** What exactly answers, for the README and XML comment: "claude-sonnet-5-5 via Anthropic API". */
  describe(): string;
  complete(req: CompletionRequest): Promise<string>;
}

export class ModelError extends Error {
  constructor(
    message: string,
    /** "setup" = fix the settings; "retry" = try again later; "refused" = change the request. */
    public readonly kind: "setup" | "retry" | "refused" | "cancelled",
  ) {
    super(message);
    this.name = "ModelError";
  }
}

export interface OpenAIPreset {
  id: string;
  label: string;
  baseUrl: string;
  modelHint: string;
  needsKey: boolean;
  note: string;
}

/**
 * Starting points for OpenAI-compatible services. Model names change often:
 * the hint is only an example, type the model your account offers.
 */
export const OPENAI_PRESETS: OpenAIPreset[] = [
  { id: "ollama", label: "Ollama (free, runs on your computer)", baseUrl: "http://localhost:11434/v1", modelHint: "llama3.1", needsKey: false, note: "Install Ollama, run `ollama pull llama3.1`, keep it running. If the browser is blocked, start Ollama with OLLAMA_ORIGINS=* ." },
  { id: "lmstudio", label: "LM Studio (free, runs on your computer)", baseUrl: "http://localhost:1234/v1", modelHint: "the model loaded in LM Studio", needsKey: false, note: "Start the local server in LM Studio and enable CORS." },
  { id: "openai", label: "OpenAI", baseUrl: "https://api.openai.com/v1", modelHint: "gpt-4o-mini", needsKey: true, note: "Needs an OpenAI API key." },
  { id: "gemini", label: "Google Gemini", baseUrl: "https://generativelanguage.googleapis.com/v1beta/openai", modelHint: "gemini-2.0-flash", needsKey: true, note: "Needs a Google AI Studio API key." },
  { id: "groq", label: "Groq", baseUrl: "https://api.groq.com/openai/v1", modelHint: "llama-3.1-8b-instant", needsKey: true, note: "Needs a Groq API key (free tier available)." },
  { id: "openrouter", label: "OpenRouter", baseUrl: "https://openrouter.ai/api/v1", modelHint: "meta-llama/llama-3.1-8b-instruct", needsKey: true, note: "Needs an OpenRouter API key; some models are free." },
  { id: "custom", label: "Other OpenAI-compatible endpoint", baseUrl: "", modelHint: "", needsKey: false, note: "Any server with a /chat/completions endpoint." },
];
