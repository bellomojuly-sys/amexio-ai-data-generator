import { BREAKERS } from "../../validate/breakers";
import type { CheckKind, CheckResult } from "../../validate/validate";
import type { Generator } from "../useGenerator";

const KIND_ORDER: CheckKind[] = ["format", "relationships", "consistency", "timeline", "target system", "privacy"];

function status(c: CheckResult): "pass" | "warn" | "fail" | "info" {
  if (c.issues.some((i) => i.severity === "error")) return "fail";
  if (c.issues.some((i) => i.severity === "warning")) return "warn";
  if (c.issues.some((i) => i.severity === "info")) return "info";
  return "pass";
}

const ICON = { pass: "✓", warn: "!", fail: "×", info: "i" };

export function ValidateStep({ gen }: { gen: Generator }) {
  const report = gen.report;
  if (!report) return null;
  const ok = report.errors === 0;
  const checks = [...report.checks].sort((a, b) => KIND_ORDER.indexOf(a.kind) - KIND_ORDER.indexOf(b.kind));
  const passed = checks.filter((c) => status(c) === "pass" || status(c) === "info").length;

  return (
    <>
      <div className="step-head">
        <div>
          <div className="eyebrow">Step 5</div>
          <h2>Validate</h2>
          <p className="lead">
            Plain code checks every document against the others, against the facts it was made from, and against what Content Server accepts. No AI judges the AI's work here. Any error blocks the export.
          </p>
        </div>
      </div>

      <section className="panel panel-pad">
        <div className="verdict">
          <div className={`verdict-mark ${ok ? "ok" : "err"}`} aria-hidden="true">{ok ? "✓" : "×"}</div>
          <div className="stack" style={{ gap: 2 }}>
            <h3 style={{ fontSize: 18 }} id="verdict">
              {ok ? "Ready to export" : `Export blocked: ${report.errors} error${report.errors === 1 ? "" : "s"}`}
            </h3>
            <span className="small muted">
              {passed} of {checks.length} checks passed · {report.warnings} warning{report.warnings === 1 ? "" : "s"} · {gen.pkg?.documents.length.toLocaleString("en-GB")} documents checked
            </span>
          </div>
          <span className="spacer" />
          <button className="btn btn-primary" id="to-export" disabled={!ok} onClick={() => gen.setStep("export")}>
            Next: export
          </button>
        </div>
      </section>

      <section className="panel">
        <div className="panel-head">
          <div>
            <h3>Try to break it</h3>
            <p className="small muted">Plant a mistake a model typically makes, and watch the checks catch it.</p>
          </div>
          {gen.breakers.length > 0 && (
            <button className="btn btn-sm" id="undo-breakers" onClick={gen.clearBreakers}>Undo all</button>
          )}
        </div>
        <div className="panel-pad stack">
          <div className="row">
            {BREAKERS.map((b) => (
              <button key={b.id} id={`break-${b.id}`} className="btn btn-sm btn-danger" onClick={() => gen.applyBreaker(b.id)} disabled={gen.breakers.some((x) => x.id === b.id)}>
                {b.label}
              </button>
            ))}
          </div>
          {gen.breakers.length > 0 && (
            <ul className="corrections">
              {gen.breakers.map((b) => (
                <li key={b.id}>
                  {b.note} <span className="muted">Expected: {BREAKERS.find((x) => x.id === b.id)?.expect}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>

      <section className="panel">
        <div className="checks">
          {checks.map((c) => {
            const s = status(c);
            const shown = c.issues.slice(0, 12);
            return (
              <div className="check-row" key={c.code}>
                <span className={`status-icon ${s}`} aria-label={s}>{ICON[s]}</span>
                <div style={{ minWidth: 0 }}>
                  <div className="row" style={{ gap: 8 }}>
                    <strong>{c.title}</strong>
                    <span className="kind-label">{c.kind}</span>
                  </div>
                  <div className="small muted">{c.description}</div>
                  {shown.length > 0 && (
                    <ul className="issues">
                      {shown.map((i, n) => (
                        <li key={n} className={i.severity}>{i.message}</li>
                      ))}
                      {c.issues.length > shown.length && <li className="muted">and {c.issues.length - shown.length} more</li>}
                    </ul>
                  )}
                </div>
                <span className="small muted num" style={{ whiteSpace: "nowrap" }}>{c.checked ? `${c.checked.toLocaleString("en-GB")} checked` : "skipped"}</span>
              </div>
            );
          })}
        </div>
      </section>
    </>
  );
}
