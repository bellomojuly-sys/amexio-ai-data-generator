/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_MODEL_PROVIDER?: string;
  readonly VITE_MODEL_API_KEY?: string;
  readonly VITE_MODEL_BASE_URL?: string;
  readonly VITE_MODEL_NAME?: string;
  readonly VITE_HOSTED?: string;
}
interface ImportMeta {
  readonly env: ImportMetaEnv;
}
