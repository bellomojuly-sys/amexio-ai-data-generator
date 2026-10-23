import type { ModelSettings, ProviderId } from "./types";
import { OPENAI_PRESETS } from "./types";

/**
 * Model settings. Defaults come from src/config/model.ts and, for the local
 * version, from .env.local (never committed). The user's choice is kept in this
 * browser only; API keys only when "Remember keys" is ticked.
 */

import { MODEL_DEFAULTS } from "../config/model";

const STORAGE_KEY = "amexio-dossier-generator.model";

export const IS_HOSTED = import.meta.env.VITE_HOSTED === "true";

export function defaultSettings(): ModelSettings {
  const env = import.meta.env;
  const envProvider = (env.VITE_MODEL_PROVIDER ?? "") as ProviderId | "";
  const provider: ProviderId = IS_HOSTED ? "claude" : envProvider || MODEL_DEFAULTS.localProvider;
  const preset = OPENAI_PRESETS.find((p) => p.id === MODEL_DEFAULTS.openai.preset) ?? OPENAI_PRESETS[0];
  return {
    provider,
    claude: { tier: MODEL_DEFAULTS.claude.tier },
    anthropic: {
      apiKey: provider === "anthropic" ? (env.VITE_MODEL_API_KEY ?? "") : "",
      model: (provider === "anthropic" && env.VITE_MODEL_NAME) || MODEL_DEFAULTS.anthropic.model,
    },
    openai: {
      preset: preset.id,
      baseUrl: (provider === "openai" && env.VITE_MODEL_BASE_URL) || MODEL_DEFAULTS.openai.baseUrl || preset.baseUrl,
      apiKey: provider === "openai" ? (env.VITE_MODEL_API_KEY ?? "") : "",
      model: (provider === "openai" && env.VITE_MODEL_NAME) || MODEL_DEFAULTS.openai.model,
    },
    rememberKeys: false,
  };
}

export function loadSettings(): ModelSettings {
  const base = defaultSettings();
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return base;
    const saved = JSON.parse(raw) as Partial<ModelSettings>;
    const merged: ModelSettings = {
      ...base,
      ...saved,
      claude: { ...base.claude, ...saved.claude },
      anthropic: { ...base.anthropic, ...saved.anthropic },
      openai: { ...base.openai, ...saved.openai },
    };
    if (!merged.rememberKeys) {
      merged.anthropic.apiKey = base.anthropic.apiKey;
      merged.openai.apiKey = base.openai.apiKey;
    }
    if (IS_HOSTED && (merged.provider === "anthropic" || merged.provider === "openai")) merged.provider = "claude";
    return merged;
  } catch {
    return base;
  }
}

export function saveSettings(s: ModelSettings): void {
  try {
    const copy: ModelSettings = JSON.parse(JSON.stringify(s));
    if (!copy.rememberKeys) {
      copy.anthropic.apiKey = "";
      copy.openai.apiKey = "";
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(copy));
  } catch {
    // Storage can be unavailable (private window); settings then last for this visit only.
  }
}
