import { readSse } from "./stream";
import type { CompletionRequest, ModelProvider, ModelSettings } from "./types";
import { ModelError } from "./types";

// ---------------------------------------------------------------------------
// Claude, through the hosted page (claude.ai "sample" capability).
// Runs on the signed-in viewer's own Claude account and limits.
// ---------------------------------------------------------------------------

type SampleFn = ((
  input: string | { role: "user" | "assistant"; content: string }[],
  options?: Record<string, unknown>,
) => Promise<{ text: string; truncated: boolean }>) & { limits?: () => Promise<unknown> };

interface ClaudeRuntime {
  use(name: "sample"): Promise<SampleFn | null>;
  use(name: "downloads"): Promise<{ save(req: { filename: string; data: Blob | string | Uint8Array }): Promise<unknown> } | null>;
}

export function claudeRuntime(): ClaudeRuntime | undefined {
  return (globalThis as unknown as { claude?: ClaudeRuntime }).claude;
}

let samplePromise: Promise<SampleFn | null> | undefined;
export function getSample(): Promise<SampleFn | null> {
  const rt = claudeRuntime();
  if (!rt?.use) return Promise.resolve(null);
  samplePromise ??= rt.use("sample").catch(() => null);
  return samplePromise;
}

const SAMPLE_ERRORS: Record<string, [string, ModelError["kind"]]> = {
  not_granted: ["You (or your organisation) have not allowed this page to use Claude. Choose another model in Model settings, or reload and allow it.", "setup"],
  sampling_disabled: ["Claude is not available for this account. Choose another model in Model settings.", "setup"],
  rate_limited: ["Claude's usage limit for your account was reached, or too many requests at once. Wait a bit and try again, or switch model.", "retry"],
  session_expired: ["Your Claude session expired. Sign in again and retry.", "setup"],
  prompt_too_large: ["The request was too large. Use fewer employees per run.", "refused"],
  refused: ["Claude declined this request. Change the scenario notes and try again.", "refused"],
  empty_completion: ["Claude returned an empty answer. Try again.", "retry"],
  cancelled: ["Stopped.", "cancelled"],
};

export function claudeProvider(settings: ModelSettings): ModelProvider {
  const tier = settings.claude.tier;
  return {
    id: "claude",
    label: "Claude (your Claude account)",
    describe: () => `Claude via claude.ai (${tier} tier, the viewer's own account)`,
    async complete(req: CompletionRequest) {
      const sample = await getSample();
      if (!sample) {
        throw new ModelError("Claude is only available inside the published Claude page. Locally, use the Anthropic API or another model.", "setup");
      }
      try {
        const { text } = await sample(`${req.system}\n\n${req.prompt}`, {
          modelTier: tier,
          signal: req.signal,
          cache: false,
          onText: ({ text: t }: { text: string }) => req.onText?.(t),
        });
        return text;
      } catch (e) {
        const err = e as { code?: string; message?: string };
        const mapped = SAMPLE_ERRORS[err.code ?? ""];
        if (mapped) throw new ModelError(mapped[0], mapped[1]);
        throw new ModelError(`Claude could not answer (${err.code ?? "error"}). Try again.`, "retry");
      }
    },
  };
}

// ---------------------------------------------------------------------------
// Anthropic API with your own key. Calls the API straight from the browser,
// which Anthropic allows only with an explicit opt-in header.
// ---------------------------------------------------------------------------

async function httpError(res: Response, service: string): Promise<ModelError> {
  let detail = "";
  try {
    const body = (await res.json()) as { error?: { message?: string } | string };
    detail = typeof body.error === "string" ? body.error : (body.error?.message ?? "");
  } catch {
    // ignore
  }
  if (res.status === 401 || res.status === 403) return new ModelError(`${service} rejected the API key. Check it in Model settings.${detail ? ` (${detail})` : ""}`, "setup");
  if (res.status === 404) return new ModelError(`${service} does not know this model or address. Check Model settings.${detail ? ` (${detail})` : ""}`, "setup");
  if (res.status === 429) return new ModelError(`${service} rate limit or quota reached. Wait and try again.${detail ? ` (${detail})` : ""}`, "retry");
  return new ModelError(`${service} returned an error (${res.status}).${detail ? ` ${detail}` : ""}`, "retry");
}

function networkError(service: string, url: string, e: unknown): ModelError {
  if ((e as Error)?.name === "AbortError") return new ModelError("Stopped.", "cancelled");
  return new ModelError(
    `Could not reach ${service} at ${url}. Check the address, that the service is running, and that it allows requests from this page (CORS).`,
    "setup",
  );
}

export function anthropicProvider(settings: ModelSettings): ModelProvider {
  const { apiKey, model } = settings.anthropic;
  return {
    id: "anthropic",
    label: "Anthropic API (your key)",
    describe: () => `${model} via Anthropic API`,
    async complete(req) {
      if (!apiKey) throw new ModelError("Add your Anthropic API key in Model settings.", "setup");
      const url = "https://api.anthropic.com/v1/messages";
      let res: Response;
      try {
        res = await fetch(url, {
          method: "POST",
          signal: req.signal,
          headers: {
            "content-type": "application/json",
            "x-api-key": apiKey,
            "anthropic-version": "2023-06-01",
            "anthropic-dangerous-direct-browser-access": "true",
          },
          body: JSON.stringify({
            model,
            max_tokens: req.maxTokens ?? 8000,
            system: req.system,
            stream: true,
            messages: [{ role: "user", content: req.prompt }],
          }),
        });
      } catch (e) {
        throw networkError("the Anthropic API", url, e);
      }
      if (!res.ok) throw await httpError(res, "The Anthropic API");
      let text = "";
      try {
        await readSse(
          res,
          (data) => {
            if (!data || data === "[DONE]") return;
            const ev = JSON.parse(data) as { type?: string; delta?: { type?: string; text?: string }; error?: { message?: string } };
            if (ev.type === "content_block_delta" && ev.delta?.text) {
              text += ev.delta.text;
              req.onText?.(text);
            }
            if (ev.type === "error") throw new ModelError(`The Anthropic API stopped: ${ev.error?.message ?? "unknown error"}`, "retry");
          },
          req.signal,
        );
      } catch (e) {
        if (e instanceof ModelError) throw e;
        throw networkError("the Anthropic API", url, e);
      }
      return text;
    },
  };
}

// ---------------------------------------------------------------------------
// Any OpenAI-compatible /chat/completions endpoint.
// ---------------------------------------------------------------------------

export function openAiProvider(settings: ModelSettings): ModelProvider {
  const { baseUrl, apiKey, model } = settings.openai;
  const base = baseUrl.replace(/\/+$/, "");
  return {
    id: "openai",
    label: "OpenAI-compatible model",
    describe: () => `${model || "model"} via ${base || "(no address)"}`,
    async complete(req) {
      if (!base) throw new ModelError("Add the service address in Model settings.", "setup");
      if (!model) throw new ModelError("Add the model name in Model settings.", "setup");
      const url = `${base}/chat/completions`;
      let res: Response;
      try {
        res = await fetch(url, {
          method: "POST",
          signal: req.signal,
          headers: { "content-type": "application/json", ...(apiKey ? { authorization: `Bearer ${apiKey}` } : {}) },
          body: JSON.stringify({
            model,
            stream: true,
            temperature: 0.8,
            max_tokens: req.maxTokens ?? 8000,
            messages: [
              { role: "system", content: req.system },
              { role: "user", content: req.prompt },
            ],
          }),
        });
      } catch (e) {
        throw networkError("the model service", url, e);
      }
      if (!res.ok) throw await httpError(res, "The model service");
      let text = "";
      try {
        await readSse(
          res,
          (data) => {
            if (!data || data === "[DONE]") return;
            const ev = JSON.parse(data) as { choices?: { delta?: { content?: string }; message?: { content?: string } }[] };
            const piece = ev.choices?.[0]?.delta?.content ?? ev.choices?.[0]?.message?.content ?? "";
            if (piece) {
              text += piece;
              req.onText?.(text);
            }
          },
          req.signal,
        );
      } catch (e) {
        if (e instanceof ModelError) throw e;
        throw networkError("the model service", url, e);
      }
      return text;
    },
  };
}

export function offlineProvider(): ModelProvider {
  return {
    id: "offline",
    label: "No AI (sample generator)",
    describe: () => "No AI (built-in sample generator)",
    async complete() {
      throw new ModelError("The sample generator does not take prompts.", "setup");
    },
  };
}

export function createProvider(settings: ModelSettings): ModelProvider {
  switch (settings.provider) {
    case "claude":
      return claudeProvider(settings);
    case "anthropic":
      return anthropicProvider(settings);
    case "openai":
      return openAiProvider(settings);
    default:
      return offlineProvider();
  }
}
