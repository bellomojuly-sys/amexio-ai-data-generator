import { useMemo, useState } from "react";
import { fullName } from "../../model/dossier";
import { docType } from "../../spec/doctypes";
import { pdfDate } from "../../spec/format";
import { renderDocument } from "../../spec/render";
import { countsByType } from "../../export/package";
import { documentNode } from "../../export/importXml";
import { renderPdf } from "../../export/pdf";
import { saveFile } from "../../export/save";
import { DocumentPage, OriginLegend } from "../components/DocumentPage";
import { XmlView } from "../components/XmlView";
import type { Generator } from "../useGenerator";

interface Props {
  gen: Generator;
  notify(message: string): void;
}

export function DocumentsStep({ gen, notify }: Props) {
  const { set, pkg } = gen;
  const [folderId, setFolderId] = useState<string | null>(null);
  const [docKey, setDocKey] = useState<string | null>(null);
  const [showOrigin, setShowOrigin] = useState(true);
  const [typeFilter, setTypeFilter] = useState<string>("all");

  const counts = useMemo(() => (pkg ? countsByType(pkg) : []), [pkg]);
  const byEmployee = useMemo(() => {
    const m = new Map<string, NonNullable<typeof pkg>["documents"]>();
    for (const d of pkg?.documents ?? []) m.set(d.employeeId, [...(m.get(d.employeeId) ?? []), d]);
    return m;
  }, [pkg]);

  if (!set || !pkg) return null;

  const employee = set.employees.find((e) => e.id === folderId) ?? set.employees[0];
  const docs = (byEmployee.get(employee.id) ?? []).filter((d) => typeFilter === "all" || d.docType === typeFilter);
  const doc = docs.find((d) => d.key === docKey) ?? docs[0];
  const rendered = doc ? renderDocument(doc, employee, set.config.target) : null;
  const max = Math.max(1, ...counts.map((c) => c.count));
  const location = `${set.config.target.rootLocation}:${set.config.target.rootFolder}`;

  async function downloadPdf() {
    if (!doc || !rendered) return;
    const bytes = await renderPdf(rendered, doc.date);
    const outcome = await saveFile(doc.fileName, bytes, "application/pdf");
    if (outcome === "saved") notify(`Saved ${doc.fileName}`);
    if (outcome === "unavailable") notify("Downloads are not available in this view");
  }

  return (
    <>
      <div className="step-head">
        <div>
          <div className="eyebrow">Step 4</div>
          <h2>Documents</h2>
          <p className="lead">
            Code turns the storylines into documents. Every name, date and amount below is read from the same facts, which is what keeps a payslip in line with its contract.
          </p>
        </div>
        <button className="btn btn-primary" id="to-validate" onClick={() => gen.setStep("validate")}>
          Next: validate
        </button>
      </div>

      <section className="panel">
        <div className="panel-head">
          <div className="estimate">
            <div>
              <div className="eyebrow">Generated</div>
              <div className="big">{pkg.documents.length.toLocaleString("en-GB")}</div>
            </div>
            <div className="small muted">
              documents in {pkg.folders.length} folders · {set.employees.filter((e) => set.storylines[e.id]?.events.some((x) => x.type === "termination")).length} employees left the company
            </div>
          </div>
        </div>
        <div className="panel-pad">
          <div className="typebars">
            {counts.map((r) => (
              <div key={r.id} style={{ display: "contents" }}>
                <span className="row" style={{ gap: 6 }}>
                  {r.label}
                  {r.origin === "extension" && <span className="badge badge-ext">Proposed</span>}
                </span>
                <div className={`typebar ${r.origin === "extension" ? "ext" : ""}`} style={{ width: `${(r.count / max) * 100}%` }} />
                <span className="num small" style={{ textAlign: "right" }}>{r.count.toLocaleString("en-GB")}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      <div className="explorer">
        <div className="col">
          <div className="col-head" title={location}>{location}</div>
          <div className="col-body" role="list" aria-label="Folders">
            {set.employees.map((e) => (
              <button
                key={e.id}
                className="folder"
                aria-current={e.id === employee.id}
                onClick={() => {
                  setFolderId(e.id);
                  setDocKey(null);
                }}
              >
                <span className="folder-icon" aria-hidden="true" />
                <span style={{ minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {e.id} {fullName(e)}
                </span>
                <span className="count">{byEmployee.get(e.id)?.length ?? 0}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="col">
          <div className="col-head" style={{ fontFamily: "var(--font-body)", display: "flex", gap: 8, alignItems: "center" }}>
            <select aria-label="Filter by type" className="select input cell" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
              <option value="all">All types ({byEmployee.get(employee.id)?.length ?? 0})</option>
              {counts.map((c) => (
                <option key={c.id} value={c.id}>{c.label}</option>
              ))}
            </select>
          </div>
          <div className="col-body" role="list" aria-label="Documents">
            {docs.map((d) => (
              <button key={d.key} className="doc-row" aria-current={doc?.key === d.key} onClick={() => setDocKey(d.key)}>
                <span className="t">{d.title}</span>
                <span className="m">
                  <span className="mono">{pdfDate(d.date)}</span>
                  <span className="type-chip">{docType(d.docType).documentType}</span>
                  {d.acl.length > 0 && <span className="badge badge-warn">Restricted</span>}
                </span>
              </button>
            ))}
            {docs.length === 0 && <div className="empty small">No documents of this type in this folder.</div>}
          </div>
        </div>

        <div className="col preview-col">
          <div className="preview-pane">
            {doc && rendered ? (
              <>
                <div className="row">
                  <div style={{ minWidth: 0 }}>
                    <div className="mono small">{doc.fileName}</div>
                    <div className="small muted">
                      {docType(doc.docType).origin === "amexio" ? "Format from AMEXIO's example" : "Proposed document type"} · {doc.confidential ? "Confidential" : "Not confidential"}
                    </div>
                  </div>
                  <span className="spacer" />
                  <label className="check small" style={{ alignItems: "center" }}>
                    <input type="checkbox" checked={showOrigin} onChange={(e) => setShowOrigin(e.target.checked)} />
                    Show where values come from
                  </label>
                  <button className="btn btn-sm" onClick={downloadPdf}>Download PDF</button>
                </div>
                {showOrigin && <OriginLegend fromAi={!/No AI|AMEXIO example/.test(`${set.provenance.personas} ${set.provenance.storylines}`)} />}
                <DocumentPage doc={rendered} showOrigin={showOrigin} />
                <div className="stack" style={{ gap: 6 }}>
                  <div className="eyebrow">Its node in import.xml</div>
                  <XmlView xml={documentNode(set, doc, "").join("\n")} />
                </div>
              </>
            ) : (
              <div className="empty">Pick a document.</div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
