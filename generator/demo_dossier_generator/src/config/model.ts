/**
 * Default model choice. Change these to switch the default for everyone who
 * runs this copy; each user can still pick another model in Model settings.
 *
 * Keys never go in this file. For your own key, create `.env.local` next to
 * package.json (it is ignored by git):
 *
 *   VITE_MODEL_PROVIDER=anthropic          # or: openai, offline
 *   VITE_MODEL_API_KEY=sk-ant-...
 *   VITE_MODEL_NAME=claude-sonnet-5-5      # optional
 *   VITE_MODEL_BASE_URL=http://localhost:11434/v1   # openai-compatible only
 *
 * The hosted Claude page always starts on "claude" (the viewer's own Claude
 * account) and never contains keys: `npm run build:artifact` blanks them.
 */
export const MODEL_DEFAULTS = {
  /** Used by the local version when .env.local does not say otherwise. */
  localProvider: "offline" as "anthropic" | "openai" | "offline",
  claude: { tier: "default" as "quick" | "default" | "complex" },
  anthropic: { model: "claude-sonnet-5-5" },
  openai: { preset: "ollama", baseUrl: "", model: "llama3.1" },
};
