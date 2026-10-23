import { claudeRuntime } from "../ai/providers";

/**
 * Offers a file to the user. Inside the hosted Claude page, downloads go
 * through the page's "downloads" capability (the viewer confirms each one);
 * in the local version, a normal browser download.
 */

type Downloads = { save(req: { filename: string; data: Blob | string | Uint8Array }): Promise<unknown> };

let downloadsPromise: Promise<Downloads | null> | undefined;

function hostedDownloads(): Promise<Downloads | null> {
  const rt = claudeRuntime();
  if (!rt?.use) return Promise.resolve(null);
  downloadsPromise ??= rt.use("downloads").catch(() => null);
  return downloadsPromise;
}

export type SaveOutcome = "saved" | "declined" | "unavailable";

export async function saveFile(filename: string, data: Blob | string | Uint8Array, mime: string): Promise<SaveOutcome> {
  const blob = data instanceof Blob ? data : new Blob([data as BlobPart], { type: mime });
  if (claudeRuntime()) {
    const downloads = await hostedDownloads();
    if (!downloads) return "unavailable";
    try {
      await downloads.save({ filename, data: blob });
      return "saved";
    } catch (e) {
      const code = (e as { code?: string }).code;
      return code === "declined" ? "declined" : "unavailable";
    }
  }
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
  return "saved";
}
