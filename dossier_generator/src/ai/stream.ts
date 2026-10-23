/** Reads a server-sent-events response line by line and hands each `data:` payload to `onData`. */
export async function readSse(response: Response, onData: (data: string) => void, signal?: AbortSignal): Promise<void> {
  if (!response.body) {
    const text = await response.text();
    for (const line of text.split("\n")) if (line.startsWith("data:")) onData(line.slice(5).trim());
    return;
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    if (signal?.aborted) {
      await reader.cancel().catch(() => {});
      throw new DOMException("Cancelled", "AbortError");
    }
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let nl: number;
    while ((nl = buffer.indexOf("\n")) >= 0) {
      const line = buffer.slice(0, nl).replace(/\r$/, "");
      buffer = buffer.slice(nl + 1);
      if (line.startsWith("data:")) onData(line.slice(5).trim());
    }
  }
  if (buffer.startsWith("data:")) onData(buffer.slice(5).trim());
}
