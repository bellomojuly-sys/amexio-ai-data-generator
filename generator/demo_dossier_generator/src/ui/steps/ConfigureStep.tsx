import { useDeferredValue, useMemo } from "react";
import { LIMITS } from "../../generate/config";
import { examplePreset } from "../../generate/examplePreset";
import { expandDossiers } from "../../generate/expand";
import { generateOffline } from "../../generate/offline";
import type { GenerationConfig } from "../../generate/types";
import { DEPARTMENTS } from "../../generate/vocab";
import { countsByType } from "../../export/package";
import { DOC_TYPES } from "../../spec/doctypes";
import type { Generator } from "../useGenerator";
import { PRESETS } from "../useGenerator";

interface Props {
  gen: Generator;
  openSettings(): void;
}

function pct(n: number) {
  return `${Math.round(n * 100)}%`;
}

export function ConfigureStep({ gen, openSettings }: Props) {
  const c = gen.config;
  const generated = !!gen.employees;

  /** Changes that alter who the people are or what happened to them clear the generated data. */
  const update = (patch: Partial<GenerationConfig>, regenerate = true) => {
    if (regenerate && generated && !gen.loaded) gen.resetGenerated();
    gen.setConfig({ ...c, ...patch });
  };

  const deferred = useDeferredValue(c);
  const loadedPkg = gen.loaded ? gen.pkg : null;
  const estimate = useMemo(() => {
    try {
      if (loadedPkg) return countsByType(loadedPkg);
      if (gen.presetId === "example") return countsByType(expandDossiers(examplePreset()));
      if (deferred.employeeCount > LIMITS.maxEmployeesOffline) return null;
      return countsByType(expandDossiers(generateOffline(deferred)));
    } catch {
      return null;
    }
  }, [deferred, gen.presetId, loadedPkg]);
  const total = estimate?.reduce((a, b) => a + b.count, 0) ?? 0;
  const max = Math.max(1, ...(estimate?.map((e) => e.count) ?? [1]));
  const isExample = gen.presetId === "example" || gen.presetId === "reference";
  const folderPicker = { webkitdirectory: "", directory: "" } as Record<string, string>;

  return (
    <>
      <div className="step-head">
        <div>
          <div className="eyebrow">Step 1</div>
          <h2>Configure the dataset</h2>
          <p className="lead">
            Pick a starting point, then adjust. The AI fills in people and careers within these limits; code turns them into PDFs and an import.xml in AMEXIO's format.
          </p>
        </div>
      </div>

      <div className="presets" role="group" aria-label="Presets">
        {PRESETS.map((p) => (
          <button key={p.id} id={`preset-${p.id}`} className="preset" aria-pressed={gen.presetId === p.id} onClick={() => gen.choosePreset(p.id)}>
            <span className="preset-title">{p.title}</span>
            <span className="small">{p.summary}</span>
            <span className="preset-meta">{p.meta}</span>
          </button>
        ))}
      </div>

      <section className="panel panel-pad stack" aria-label="Open cases">
        <div className="section-title">
          <h3>Or open cases from the case model</h3>
          <span className="small muted">one folder per employee: case.json, cast.json, storyline.json, documents.json</span>
        </div>
        <div className="row">
          <button className="btn" id="load-reference" aria-pressed={gen.presetId === "reference"} onClick={gen.loadReference}>
            Reference case 100101
          </button>
          <label className="btn" id="open-case-folder">
            Open case folder…
            <input type="file" multiple hidden {...folderPicker} onChange={(e) => e.target.files?.length && gen.loadCaseFiles(e.target.files)} />
          </label>
          <label className="btn" id="open-case-zip">
            Open exported ZIP…
            <input type="file" accept=".zip" hidden onChange={(e) => e.target.files?.length && gen.loadCaseFiles(e.target.files)} />
          </label>
        </div>
        <span className="help">
          The reference case is AMEXIO's 100101 as the case model builds it (<code>case_model/reference_dossier.golden.json</code>); rendering it gives AMEXIO's five PDFs and import.xml entries (BR-14). A folder written by <code>python -m case_model.ingest</code>, or a ZIP this demo exported, opens the same way. Every generated run also goes through case folders before any document is made.
        </span>
        {gen.loadError && <div className="callout err">{gen.loadError}</div>}
        {gen.loaded && (
          <div className="callout">
            Opened {gen.loaded.cases.length} case{gen.loaded.cases.length === 1 ? "" : "s"} from {gen.loaded.source}.{" "}
            {gen.loaded.followConfig ? "The period, document types and import options below apply." : "AMEXIO's example settings apply."}{" "}
            {gen.stage && gen.stage.read.problems.length > 0 && `${gen.stage.read.problems.length} problem${gen.stage.read.problems.length === 1 ? "" : "s"} found: see Validate.`}
          </div>
        )}
      </section>

      {isExample ? (
        <div className="callout">
          {gen.presetId === "reference"
            ? "The reference case is read with AMEXIO's example settings: one document per type, data as of 30 September 2026, the contract under version control and the update node of the example."
            : "This preset loads AMEXIO's four example employees as fixed input. Generating from it rebuilds the 20 documents and the import.xml of the mock package, including its special cases (version control, a Dutch title, an \"&\" in a title, sync and update). It is the generator's proof that it understands the format."}
        </div>
      ) : (
        <div className="grid-2">
          <section className="panel panel-pad stack">
            <h3>Company and period</h3>
            <div className="grid-2">
              <div className="field">
                <label htmlFor="cfg-employees">Employees</label>
                <input
                  id="cfg-employees"
                  className="input num"
                  type="number"
                  min={1}
                  max={LIMITS.maxEmployeesOffline}
                  value={c.employeeCount}
                  onChange={(e) => update({ employeeCount: Math.max(1, Math.min(LIMITS.maxEmployeesOffline, Number(e.target.value) || 1)) })}
                />
                <span className="help">
                  Each gets a folder (dossier). With a model, at most {LIMITS.maxEmployeesWithAi} per run.
                </span>
              </div>
              <div className="field">
                <label htmlFor="cfg-seed">Seed</label>
                <input id="cfg-seed" className="input num" type="number" value={c.seed} onChange={(e) => update({ seed: Number(e.target.value) || 0 })} />
                <span className="help">Same seed and settings, same dataset (in No AI mode).</span>
              </div>
              <div className="field">
                <label htmlFor="cfg-asof">Data as of</label>
                <input id="cfg-asof" className="input" type="date" value={c.asOf} onChange={(e) => e.target.value && update({ asOf: e.target.value })} />
              </div>
              <div className="field">
                <label htmlFor="cfg-hire">Earliest hire date</label>
                <input id="cfg-hire" className="input" type="date" value={c.earliestHire} onChange={(e) => e.target.value && update({ earliestHire: e.target.value })} />
              </div>
            </div>
            <div className="field">
              <span className="label">Departments</span>
              <div className="chips">
                {DEPARTMENTS.map((d) => {
                  const on = c.departments.includes(d.name);
                  return (
                    <button
                      key={d.name}
                      className="chip-toggle"
                      aria-pressed={on}
                      onClick={() => {
                        const next = on ? c.departments.filter((x) => x !== d.name) : [...c.departments, d.name];
                        if (next.length) update({ departments: DEPARTMENTS.map((x) => x.name).filter((n) => next.includes(n)) });
                      }}
                    >
                      {d.name}
                    </button>
                  );
                })}
              </div>
              <span className="help">Positions, salary ranges and courses per department are fixed lists; the AI chooses within them.</span>
            </div>
          </section>

          <section className="panel panel-pad stack">
            <h3>History and scenarios</h3>
            <div className="field">
              <span className="label">Documents per employee</span>
              <div className="seg" role="group" aria-label="History">
                <button aria-pressed={c.history === "latest"} onClick={() => update({ history: "latest" })}>One per type</button>
                <button aria-pressed={c.history === "full"} onClick={() => update({ history: "full" })}>Full history</button>
              </div>
              <span className="help">
                "One per type" matches AMEXIO's example. "Full history" adds monthly payslips, yearly appraisals and statements.
              </span>
            </div>
            {c.history === "full" && (
              <div className="field">
                <label htmlFor="cfg-years">Years of history: {c.historyYears}</label>
                <input id="cfg-years" type="range" min={1} max={LIMITS.maxHistoryYears} value={c.historyYears} onChange={(e) => update({ historyYears: Number(e.target.value) })} />
              </div>
            )}
            {(
              [
                ["leaverShare", "Leave the company"],
                ["temporaryShare", "Start on a temporary contract"],
                ["partTimeShare", "Work part time"],
                ["absenceShare", "Have sick leave"],
              ] as const
            ).map(([key, label]) => (
              <div className="field" key={key}>
                <label htmlFor={`cfg-${key}`}>{label}</label>
                <div className="range-row">
                  <input id={`cfg-${key}`} type="range" min={0} max={0.6} step={0.05} value={c.scenario[key]} onChange={(e) => update({ scenario: { ...c.scenario, [key]: Number(e.target.value) } })} />
                  <span className="num small">{pct(c.scenario[key])}</span>
                </div>
              </div>
            ))}
            <label className="check">
              <input type="checkbox" checked={c.scenario.promotions} onChange={(e) => update({ scenario: { ...c.scenario, promotions: e.target.checked } })} />
              <span>Promotions</span>
            </label>
            <label className="check">
              <input type="checkbox" checked={c.scenario.appraisalComments} onChange={(e) => update({ scenario: { ...c.scenario, appraisalComments: e.target.checked } })} />
              <span>
                AI-written manager comments on appraisals
                <span className="help" style={{ display: "block" }}>The only free text the AI writes. Checked for numbers and health details.</span>
              </span>
            </label>
          </section>
        </div>
      )}

      {!isExample && (
        <div className="grid-2">
          <section className="panel panel-pad stack">
            <div className="section-title">
              <h3>Document types</h3>
              <span className="small muted">{c.docTypes.length} of {DOC_TYPES.length}</span>
            </div>
            <div className="stack" style={{ gap: 10 }}>
              {DOC_TYPES.map((d) => (
                <label className="check" key={d.id}>
                  <input
                    type="checkbox"
                    checked={c.docTypes.includes(d.id)}
                    onChange={(e) => {
                      const next = e.target.checked ? [...c.docTypes, d.id] : c.docTypes.filter((x) => x !== d.id);
                      update({ docTypes: DOC_TYPES.map((x) => x.id).filter((id) => next.includes(id)) }, false);
                    }}
                  />
                  <span>
                    <span className="row" style={{ gap: 8 }}>
                      <strong>{d.documentType}</strong>
                      {d.origin === "amexio" ? <span className="badge badge-amexio">In AMEXIO's example</span> : <span className="badge badge-ext">Proposed</span>}
                    </span>
                    <span className="help" style={{ display: "block" }}>{d.occurs}</span>
                  </span>
                </label>
              ))}
            </div>
          </section>

          <section className="panel panel-pad stack">
            <h3>Notes for the AI</h3>
            <div className="field">
              <label htmlFor="cfg-notes">Scenario notes (optional)</label>
              <textarea
                id="cfg-notes"
                className="textarea"
                rows={3}
                maxLength={600}
                placeholder="For example: a fast-growing IT team with many young developers; Logistics has high turnover."
                value={c.scenarioNotes}
                onChange={(e) => update({ scenarioNotes: e.target.value })}
              />
              <span className="help">Passed to the model as data, never as instructions. Limits above still apply.</span>
            </div>
            <details className="disclosure">
              <summary>Import options</summary>
              <div className="disclosure-body stack">
                <div className="grid-2">
                  <div className="field">
                    <label htmlFor="cfg-package">Package name</label>
                    <input id="cfg-package" className="input mono" value={c.target.packageName} onChange={(e) => update({ target: { ...c.target, packageName: e.target.value.replace(/[^A-Za-z0-9_-]/g, "") || "hr-dossier-import" } }, false)} />
                  </div>
                  <div className="field">
                    <label htmlFor="cfg-base">Server folder</label>
                    <input id="cfg-base" className="input mono" value={c.target.basePath} onChange={(e) => update({ target: { ...c.target, basePath: e.target.value } }, false)} />
                  </div>
                </div>
                <label className="check">
                  <input type="checkbox" checked={c.importOptions.versionControlContracts} onChange={(e) => update({ importOptions: { ...c.importOptions, versionControlContracts: e.target.checked } }, false)} />
                  <span>Store contracts as major version 1.0</span>
                </label>
                <label className="check">
                  <input type="checkbox" checked={c.importOptions.dutchTitles} onChange={(e) => update({ importOptions: { ...c.importOptions, dutchTitles: e.target.checked } }, false)} />
                  <span>Add Dutch titles (title language="nl")</span>
                </label>
                <label className="check">
                  <input type="checkbox" checked={c.importOptions.action === "sync"} onChange={(e) => update({ importOptions: { ...c.importOptions, action: e.target.checked ? "sync" : "create" } }, false)} />
                  <span>Use action="sync" so the import can run twice</span>
                </label>
                <label className="check">
                  <input type="checkbox" checked={c.importOptions.includeUpdateExample} onChange={(e) => update({ importOptions: { ...c.importOptions, includeUpdateExample: e.target.checked } }, false)} />
                  <span>Add an action="update" example at the end</span>
                </label>
                <div className="small muted">
                  Target system (from AMEXIO's example, must already exist): category <code>{c.target.categoryName}</code>, user <code>{c.target.createdBy}</code>, group <code>{c.target.knownGroups.join(", ")}</code>.
                </div>
              </div>
            </details>
          </section>
        </div>
      )}

      <section className="panel">
        <div className="panel-head">
          <div className="estimate">
            <div>
              <div className="eyebrow">Expected output</div>
              <div className="big">{estimate ? `≈ ${total.toLocaleString("en-GB")}` : "—"}</div>
            </div>
            <div className="small muted" style={{ maxWidth: "46ch" }}>
              documents in {(gen.loaded ? gen.loaded.cases.length : c.employeeCount) + 1} folders{isExample || gen.loaded ? "" : ", estimated with the sample generator; an AI run lands close to this"}.
            </div>
          </div>
          <div className="row">
            {!gen.forcedOffline && (
              <button className="btn" onClick={openSettings}>
                Model: {gen.provider.label}
              </button>
            )}
            <button className="btn btn-primary" id="to-personas" onClick={() => gen.setStep("personas")}>
              Next: personas
            </button>
          </div>
        </div>
        {estimate && (
          <div className="panel-pad">
            <div className="typebars">
              {estimate.map((r) => (
                <div key={r.id} style={{ display: "contents" }}>
                  <span>{r.label}</span>
                  <div className={`typebar ${r.origin === "extension" ? "ext" : ""}`} style={{ width: `${(r.count / max) * 100}%` }} />
                  <span className="num small" style={{ textAlign: "right" }}>{r.count.toLocaleString("en-GB")}</span>
                </div>
              ))}
            </div>
          </div>
        )}
        {gen.aiLimitExceeded && (
          <div className="panel-pad" style={{ paddingTop: 0 }}>
            <div className="callout warn">
              {c.employeeCount} employees is more than the {LIMITS.maxEmployeesWithAi} a model run allows in this demo. Lower the number, or switch to "No AI" in Model settings for large volumes.
            </div>
          </div>
        )}
      </section>
    </>
  );
}
