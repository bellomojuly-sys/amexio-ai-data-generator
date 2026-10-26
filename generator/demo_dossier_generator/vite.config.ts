import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { viteSingleFile } from "vite-plugin-singlefile";

// Two builds from one codebase:
//  - `npm run dev` / `npm run build`: the local app. Model settings may come from .env.local.
//  - `npm run build:artifact`: one self-contained HTML file for the hosted Claude demo.
//    API keys and other VITE_MODEL_* values are blanked so they can never end up in a published page.
export default defineConfig(({ mode }) => {
  const artifact = mode === "artifact";
  return {
    plugins: [react(), ...(artifact ? [viteSingleFile()] : [])],
    define: artifact
      ? {
          "import.meta.env.VITE_MODEL_PROVIDER": JSON.stringify(""),
          "import.meta.env.VITE_MODEL_API_KEY": JSON.stringify(""),
          "import.meta.env.VITE_MODEL_BASE_URL": JSON.stringify(""),
          "import.meta.env.VITE_MODEL_NAME": JSON.stringify(""),
          "import.meta.env.VITE_HOSTED": JSON.stringify("true"),
        }
      : {},
    build: artifact
      ? { outDir: "dist-artifact", assetsInlineLimit: 100_000_000, cssCodeSplit: false, chunkSizeWarningLimit: 2000 }
      : { outDir: "dist", chunkSizeWarningLimit: 2000 },
  };
});
