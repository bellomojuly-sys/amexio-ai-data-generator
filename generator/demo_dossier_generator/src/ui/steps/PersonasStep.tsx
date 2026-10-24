import { fullName } from "../../model/dossier";
import type { Employee } from "../../model/dossier";
import { CorrectionsList, Exchanges, RunStatus } from "../components/RunPanel";
import type { Generator } from "../useGenerator";

interface Props {
  gen: Generator;
  openSettings(): void;
}

export function PersonasStep({ gen, openSettings }: Props) {
  const running = gen.personaRun.status === "running";
  const isExample = gen.presetId === "example";
  const fromCases = !!gen.loaded;
  const offline = gen.provider.id === "offline";
  const actionLabel = isExample
    ? "Load AMEXIO's 4 employees"
    : gen.employees
      ? `Regenerate with ${offline ? "the sample generator" : gen.provider.label}`
      : `Generate with ${offline ? "the sample generator" : gen.provider.label}`;

  return (
    <>
      <div className="step-head">
        <div>
          <div className="eyebrow">Step 2</div>
          <h2>Personas</h2>
          <p className="lead">
            The model proposes the people: names, departments, positions, hire dates and salaries. Code then assigns personnel numbers, links each employee to their manager, decides who leaves, and corrects anything outside the allowed lists.
          </p>
        </div>
      </div>

      {fromCases ? (
        <section className="panel panel-pad stack">
          <div className="callout">
            Read from <strong>{gen.loaded!.source}</strong>: {gen.employees?.length ?? 0} case{gen.employees?.length === 1 ? "" : "s"}. The people, the jobs and the managers below are the facts these cases hold; nothing is generated.
          </div>
          {gen.caseError && <div className="callout err">{gen.caseError}</div>}
        </section>
      ) : (
      <section className="panel panel-pad stack">
        <div className="row">
          <button className="btn btn-primary" id="generate-personas" onClick={gen.generatePersonas} disabled={running || gen.aiLimitExceeded}>
            {actionLabel}
          </button>
          {!isExample && !gen.forcedOffline && (
            <button className="btn btn-quiet" onClick={openSettings}>Change model</button>
          )}
          <span className="spacer" />
          {gen.employees && !running && (
            <span className="small muted">From: {gen.personaSource}</span>
          )}
        </div>
        {gen.aiLimitExceeded && (
          <div className="callout warn">Too many employees for a model run. Lower the number in Configure, or switch to No AI.</div>
        )}
        <RunStatus run={gen.personaRun} onStop={gen.stop} offline={offline || isExample} />
        {gen.personaRun.status === "error" && gen.personaRun.errorKind === "setup" && (
          <div className="row">
            <button className="btn" onClick={openSettings}>Open model settings</button>
          </div>
        )}
        <CorrectionsList corrections={gen.personaCorrections} title="Personas" />
        <Exchanges exchanges={gen.exchanges.filter((x) => x.label === "Personas")} />
      </section>
      )}

      {gen.employees ? (
        <>
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Name</th>
                  <th>Department</th>
                  <th>Position at hire</th>
                  <th>Hired</th>
                  <th>Contract</th>
                  <th className="num">Hours</th>
                  <th className="num">Salary (EUR)</th>
                  <th>Reports to</th>
                  <th>Leaves</th>
                </tr>
              </thead>
              <tbody>
                {gen.employees.map((e) => (
                  <PersonaRow key={e.id} e={e} all={gen.employees!} director={gen.config.company.directorName} />
                ))}
              </tbody>
            </table>
          </div>
          <div className="row">
            <span className="small muted">
              Read-only: these facts go into the case model as they are (one case per employee, P001 is the employee, P002 the manager). To change them, change the configuration and generate again.
            </span>
            <span className="spacer" />
            <button className="btn btn-primary" id="to-storylines" onClick={() => gen.setStep("storylines")}>
              Next: storylines
            </button>
          </div>
        </>
      ) : (
        !running && (
          <div className="panel empty">
            <strong>No personas yet</strong>
            <span>Generate them to see who works at {gen.config.company.employerName.replace(" (fictional)", "")}.</span>
          </div>
        )
      )}
    </>
  );
}

function PersonaRow({ e, all, director }: { e: Employee; all: Employee[]; director: string }) {
  const manager = e.managerId ? all.find((m) => m.id === e.managerId) : undefined;
  return (
    <tr>
      <td className="mono">{e.id}</td>
      <td style={{ minWidth: 160 }}>{fullName(e)}</td>
      <td>
        {e.department}
        {e.isManager && <span className="badge badge-info" style={{ marginLeft: 6 }}>Manager</span>}
      </td>
      <td>{e.position}</td>
      <td className="mono">{e.hireDate}</td>
      <td>{e.contractType}</td>
      <td className="num">{e.hoursPerWeek}</td>
      <td className="num">{e.startSalary.toLocaleString("en-GB")}</td>
      <td className="small">{manager ? `${manager.id} ${fullName(manager)}` : (e.managerName ?? director)}</td>
      <td>{e.leaves ? "Yes" : "No"}</td>
    </tr>
  );
}
