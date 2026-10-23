import { useEffect, useRef, useState } from "react";
import type { ModelExchange } from "../../generate/pipeline";
import type { Correction } from "../../model/dossier";
import type { RunState } from "../useGenerator";

export function useElapsed(run: RunState): number {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (run.status !== "running") return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [run.status]);
  return run.startedAt ? Math.max(0, Math.round((now - run.startedAt) / 1000)) : 0;
}

export function RunStatus({ run, onStop, offline }: { run: RunState; onStop(): void; offline: boolean }) {
  const elapsed = useElapsed(run);
  const streamRef = useRef<HTMLPreElement>(null);
  useEffect(() => {
    if (streamRef.current) streamRef.current.scrollTop = streamRef.current.scrollHeight;
  }, [run.stream]);
  if (run.status === "idle") return null;
  return (
    <div className="run">
      {run.status === "running" && (
        <div className="run-status">
          <span className="spinner" aria-hidden="true" />
          <span>
            {run.label ?? "Working"}
            {run.progress ? ` · ${run.progress[0]} of ${run.progress[1]} employees` : ""}
            {!offline && ` · ${elapsed}s`}
            {!offline && !run.stream && " · the model is thinking before it writes"}
          </span>
          <span className="spacer" />
          {!offline && (
            <button className="btn btn-sm" onClick={onStop}>Stop</button>
          )}
        </div>
      )}
      {run.status === "error" && (
        <div className="callout err">
          <strong>{run.errorKind === "setup" ? "Check the model settings. " : ""}</strong>
          {run.error}
        </div>
      )}
      {run.stream && run.status === "running" && (
        <pre className="stream" ref={streamRef} aria-live="off">{run.stream}</pre>
      )}
    </div>
  );
}

export function Exchanges({ exchanges }: { exchanges: ModelExchange[] }) {
  if (!exchanges.length) return null;
  return (
    <details className="disclosure">
      <summary>What was sent to the model, and what came back ({exchanges.length} request{exchanges.length === 1 ? "" : "s"})</summary>
      <div className="disclosure-body stack">
        {exchanges.map((x, i) => (
          <div key={i} className="stack" style={{ gap: 6 }}>
            <div className="eyebrow">{x.label} · prompt</div>
            <pre className="stream" style={{ maxHeight: 260 }}>{x.prompt}</pre>
            <div className="eyebrow">{x.label} · answer</div>
            <pre className="stream" style={{ maxHeight: 260 }}>{x.answer}</pre>
          </div>
        ))}
      </div>
    </details>
  );
}

export function CorrectionsList({ corrections, title }: { corrections: Correction[]; title: string }) {
  const fixes = corrections.filter((c) => c.kind !== "rule");
  const rules = corrections.filter((c) => c.kind === "rule");
  if (!corrections.length) return null;
  return (
    <div className={`callout ${fixes.length ? "warn" : ""}`}>
      <div className="stack" style={{ gap: 8 }}>
        {fixes.length > 0 && (
          <details className="disclosure" open={fixes.length <= 6}>
            <summary>
              {title}: code corrected {fixes.length} value{fixes.length === 1 ? "" : "s"} the model proposed
            </summary>
            <ul className="corrections disclosure-body">
              {fixes.map((c, i) => (
                <li key={i}>{c.message}</li>
              ))}
            </ul>
          </details>
        )}
        {rules.length > 0 && (
          <details className="disclosure">
            <summary>
              {rules.length} business rule{rules.length === 1 ? "" : "s"} applied by code
            </summary>
            <ul className="corrections disclosure-body">
              {rules.map((c, i) => (
                <li key={i}>{c.message}</li>
              ))}
            </ul>
          </details>
        )}
      </div>
    </div>
  );
}
