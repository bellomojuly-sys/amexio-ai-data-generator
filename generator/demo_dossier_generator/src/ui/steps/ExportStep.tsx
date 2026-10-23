import { useRef, useState } from "react";
import { buildZip, countsByType, generationRecord } from "../../export/package";
import type { PackageProgress } from "../../export/package";
import { saveFile } from "../../export/save";
import { formatSpec } from "../../spec/exportSpec";
import { XmlView } from "../components/XmlView";
import type { Generator } from "../useGenerator";

interface Props {
  gen: Generator;
  notify(message: string): void;
}

export function ExportStep({ gen, notify }: Props) {
  const { set, pkg, report, xml } = gen;
  const [progress, setProgress] = useState<PackageProgress | null>(null);
  const [busy, setBusy] = useState(false);
  const ctl = useRef<AbortController | null>(null);
  if (!set || !pkg || !report) return null;

  const blocked = report.errors > 0;
  const name = set.config.target.packageName;
  const counts = countsByType(pkg);
  const sample = pkg.documents.slice(0, 3).map((d) => d.fileName);

  async function report_(outcome: string, file: string) {
    if (outcome === "saved") notify(`Saved ${file}`);
    else if (outcome === "declined") notify("Download cancelled");
    else notify("Downloads are not available in this view");
  }

  async function downloadZip() {
    if (!set || !pkg) return;
    setBusy(true);
    ctl.current = new AbortController();
    try {
      const zip = await buildZip(set, pkg, setProgress, ctl.current.signal);
      const outcome = await saveFile(`${name}.zip`, zip, "application/zip");
      await report_(outcome, `${name}.zip`);
    } catch (e) {
      if ((e as Error)?.name !== "AbortError") notify(`Export failed: ${(e as Error)?.message ?? e}`);
    } finally {
      setBusy(false);
      setProgress(null);
    }
  }

  const tree = [
    `${name}/`,
    `├── README.md`,
    `├── import.xml          ${pkg.folders.length} folders, ${pkg.documents.length} documents${pkg.updates.length ? `, ${pkg.updates.length} update` : ""}`,
    `├── generation.json     the facts every document was made from`,
    `└── files/              ${pkg.documents.length} PDFs`,
    ...sample.map((f, i) => `    ${i === sample.length - 1 && pkg.documents.length <= 3 ? "└──" : "├──"} ${f}`),
    ...(pkg.documents.length > 3 ? [`    └── ... ${pkg.documents.length - 3} more`] : []),
  ].join("\n");

  return (
    <>
      <div className="step-head">
        <div>
          <div className="eyebrow">Step 6</div>
          <h2>Export</h2>
          <p className="lead">
            The package has the same layout as AMEXIO's example: unpack it to <code>{set.config.target.basePath}</code> on the Object Importer server and run <code>import.xml</code>.
          </p>
        </div>
      </div>

      {blocked ? (
        <div className="callout err">
          Export is blocked: validation found {report.errors} error{report.errors === 1 ? "" : "s"}.{" "}
          <button className="btn btn-sm" onClick={() => gen.setStep("validate")}>Back to validation</button>
        </div>
      ) : (
        <div className="grid-2">
          <section className="panel panel-pad stack">
            <h3>Import package</h3>
            <pre className="tree">{tree}</pre>
            <div className="small muted">
              {counts.map((c) => `${c.count.toLocaleString("en-GB")} ${c.label}`).join(" · ")}
            </div>
            {progress && (
              <div className="stack" style={{ gap: 6 }}>
                <div className="progress" aria-label="Export progress">
                  <div style={{ width: `${Math.round((progress.done / Math.max(1, progress.total)) * 100)}%` }} />
                </div>
                <span className="small muted num">
                  {progress.phase === "pdf" ? `Drawing PDFs: ${progress.done.toLocaleString("en-GB")} of ${progress.total.toLocaleString("en-GB")}` : "Packing the ZIP"}
                </span>
              </div>
            )}
            <div className="row">
              <button className="btn btn-primary" id="download-zip" onClick={downloadZip} disabled={busy}>
                {busy ? "Building..." : `Download ${name}.zip`}
              </button>
              {busy && (
                <button className="btn btn-sm" onClick={() => ctl.current?.abort()}>Cancel</button>
              )}
            </div>
          </section>

          <section className="panel panel-pad stack">
            <h3>Separate files</h3>
            <p className="small muted">For a quick look, or to share the format with the team.</p>
            <div className="stack" style={{ gap: 8 }}>
              <button className="btn" id="download-xml" onClick={async () => report_(await saveFile("import.xml", xml, "application/xml"), "import.xml")}>
                import.xml only
              </button>
              <button className="btn" onClick={async () => report_(await saveFile("generation.json", JSON.stringify(generationRecord(set), null, 2), "application/json"), "generation.json")}>
                generation.json (personas and storylines)
              </button>
              <button className="btn" onClick={async () => report_(await saveFile("format-spec.json", JSON.stringify(formatSpec(), null, 2), "application/json"), "format-spec.json")}>
                format-spec.json (the format, machine-readable)
              </button>
            </div>
          </section>
        </div>
      )}

      <section className="panel panel-pad stack">
        <div className="section-title">
          <h3>import.xml</h3>
          <span className="small muted">{xml.split("\n").length.toLocaleString("en-GB")} lines · built by code, never by the model</span>
        </div>
        <XmlView xml={xml} maxLines={160} />
      </section>
    </>
  );
}
