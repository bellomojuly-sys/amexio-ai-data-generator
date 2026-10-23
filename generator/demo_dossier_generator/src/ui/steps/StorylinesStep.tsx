import { useState } from "react";
import type { CareerEvent, Rating } from "../../model/dossier";
import { eventDate, fullName, RATINGS } from "../../model/dossier";
import { eurGrouped, pdfDate } from "../../spec/format";
import { CorrectionsList, Exchanges, RunStatus } from "../components/RunPanel";
import type { Generator } from "../useGenerator";

interface Props {
  gen: Generator;
  openSettings(): void;
}

const KIND_LABEL: Record<CareerEvent["type"], string> = {
  contract_change: "Contract change",
  training: "Training",
  appraisal: "Appraisal",
  medical_check: "Medical check",
  absence: "Sick leave",
  termination: "Leaves the company",
};

function describe(e: CareerEvent): string {
  switch (e.type) {
    case "contract_change": {
      const parts = [
        e.newPosition && `becomes ${e.newPosition}`,
        e.newSalary && `salary ${eurGrouped(e.newSalary)}`,
        e.newContractType && `${e.newContractType.toLowerCase()} contract`,
        e.newHours && `${e.newHours} hours a week`,
      ].filter(Boolean);
      return `${e.reason}: ${parts.join(", ")}`;
    }
    case "training":
      return `${e.course} · ${e.durationDays} day${e.durationDays === 1 ? "" : "s"}`;
    case "appraisal":
      return e.rating;
    case "medical_check":
      return `${e.result} · scheduled by code (every 2 years)`;
    case "absence":
      return e.endDate ? `Until ${pdfDate(e.endDate)}` : "Not yet returned";
    case "termination":
      return `${e.reason} · last working day`;
  }
}

export function StorylinesStep({ gen, openSettings }: Props) {
  const [selected, setSelected] = useState<string | null>(null);
  const running = gen.storyRun.status === "running";
  const isExample = gen.presetId === "example";
  const offline = gen.provider.id === "offline";
  const employees = gen.employees ?? [];
  const current = employees.find((e) => e.id === selected) ?? employees[0];
  const story = current && gen.storylines?.[current.id];

  const label = isExample
    ? "Load the example's events"
    : `${gen.storylines ? "Regenerate" : "Write"} storylines with ${offline ? "the sample generator" : gen.provider.label}`;

  const removeEvent = (index: number) => {
    if (!story || !current) return;
    gen.updateStoryline(current.id, { ...story, events: story.events.filter((_, i) => i !== index) });
  };
  const patchEvent = (index: number, patch: Partial<CareerEvent>) => {
    if (!story || !current) return;
    gen.updateStoryline(current.id, { ...story, events: story.events.map((ev, i) => (i === index ? ({ ...ev, ...patch } as CareerEvent) : ev)) });
  };

  return (
    <>
      <div className="step-head">
        <div>
          <div className="eyebrow">Step 3</div>
          <h2>Storylines</h2>
          <p className="lead">
            For each employee the model writes what happened since they were hired: raises and promotions, trainings, sick leave, appraisal ratings and comments, and for some, leaving. Code schedules the medical checks, enforces dates and ranges, and fills any gaps.
          </p>
        </div>
      </div>

      <section className="panel panel-pad stack">
        <div className="row">
          <button className="btn btn-primary" id="generate-storylines" onClick={gen.generateStorylines} disabled={running || !gen.employees}>
            {label}
          </button>
          {!isExample && !gen.forcedOffline && (
            <button className="btn btn-quiet" onClick={openSettings}>Change model</button>
          )}
          <span className="spacer" />
          {gen.storylines && !running && <span className="small muted">From: {gen.storySource}</span>}
        </div>
        {!offline && !isExample && !gen.storylines && !running && (
          <p className="small muted">
            {employees.length} employees are sent in {Math.ceil(employees.length / 5)} request{Math.ceil(employees.length / 5) === 1 ? "" : "s"} of up to five.
          </p>
        )}
        <RunStatus run={gen.storyRun} onStop={gen.stop} offline={offline || isExample} />
        <CorrectionsList corrections={gen.storyCorrections} title="Storylines" />
        <Exchanges exchanges={gen.exchanges.filter((x) => x.label.startsWith("Storylines"))} />
      </section>

      {gen.storylines && current ? (
        <>
          <div className="split">
            <div className="panel">
              <div className="list" role="list">
                {employees.map((e) => {
                  const s = gen.storylines![e.id];
                  const leaves = s?.events.find((x) => x.type === "termination");
                  return (
                    <button key={e.id} className="list-item" aria-current={e.id === current.id} onClick={() => setSelected(e.id)}>
                      <span className="title">
                        <span className="mono small muted">{e.id}</span> {fullName(e)}
                        {leaves && <span className="badge badge-leaver">left {leaves.type === "termination" ? leaves.date.slice(0, 7) : ""}</span>}
                      </span>
                      <span className="small muted">
                        {e.position} · {s?.events.length ?? 0} events
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="panel">
              <div className="panel-head">
                <div>
                  <h3>
                    {current.id} {fullName(current)}
                  </h3>
                  <div className="small muted">
                    {current.position}, {current.department} · hired {pdfDate(current.hireDate)} · {current.contractType}, {current.hoursPerWeek} h · {eurGrouped(current.startSalary)}
                  </div>
                </div>
              </div>
              <div className="panel-pad">
                <ol className="timeline">
                  <li className="tl-item">
                    <span className="tl-date">{pdfDate(current.hireDate)}</span>
                    <span className="tl-dot" aria-hidden="true" />
                    <div className="tl-body">
                      <span className="tl-kind">Hired</span>
                      <span className="tl-detail">Employment contract signed</span>
                    </div>
                    <span />
                  </li>
                  {story?.events.map((ev, i) => (
                    <li className="tl-item" key={`${ev.type}-${eventDate(ev)}-${i}`}>
                      <span className="tl-date">{ev.type === "appraisal" ? `${ev.year}` : pdfDate(eventDate(ev))}</span>
                      <span className={`tl-dot t-${ev.type}`} aria-hidden="true" />
                      <div className="tl-body">
                        <span className="tl-kind">{KIND_LABEL[ev.type]}</span>
                        {ev.type === "appraisal" && !isExample ? (
                          <>
                            <select aria-label="Rating" className="select input cell" style={{ maxWidth: 240 }} value={ev.rating} onChange={(e) => patchEvent(i, { rating: e.target.value as Rating })}>
                              {RATINGS.map((r) => (
                                <option key={r}>{r}</option>
                              ))}
                            </select>
                            {ev.comment !== undefined && (
                              <textarea aria-label="Manager comment" className="textarea" rows={2} value={ev.comment} onChange={(e) => patchEvent(i, { comment: e.target.value })} />
                            )}
                          </>
                        ) : (
                          <span className="tl-detail">{describe(ev)}</span>
                        )}
                      </div>
                      <span className="tl-actions">
                        {!isExample && ev.type !== "appraisal" && ev.type !== "medical_check" && (
                          <button className="btn btn-sm btn-quiet" aria-label={`Remove ${KIND_LABEL[ev.type]}`} onClick={() => removeEvent(i)}>
                            Remove
                          </button>
                        )}
                      </span>
                    </li>
                  ))}
                </ol>
              </div>
            </div>
          </div>
          <div className="row">
            <span className="small muted">Edits here flow straight into the documents. The validator re-checks everything.</span>
            <span className="spacer" />
            <button className="btn btn-primary" id="to-documents" onClick={() => gen.setStep("documents")}>
              Next: documents
            </button>
          </div>
        </>
      ) : (
        !running && (
          <div className="panel empty">
            <strong>No storylines yet</strong>
            <span>Write them to see each employee's career, from contract to last payslip.</span>
          </div>
        )
      )}
    </>
  );
}
