import { fullName } from "../../model/dossier";
import type { Employee } from "../../model/dossier";
import { department } from "../../generate/vocab";
import { CorrectionsList, Exchanges, RunStatus } from "../components/RunPanel";
import type { Generator } from "../useGenerator";

interface Props {
  gen: Generator;
  openSettings(): void;
}

export function PersonasStep({ gen, openSettings }: Props) {
  const running = gen.personaRun.status === "running";
  const isExample = gen.presetId === "example";
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
                  <PersonaRow key={e.id} e={e} all={gen.employees!} director={gen.config.company.directorName} locked={isExample} onChange={(patch) => gen.updateEmployee(e.id, patch)} />
                ))}
              </tbody>
            </table>
          </div>
          <div className="row">
            <span className="small muted">
              Editing a person clears the storylines, because those were written for the old facts.
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

function PersonaRow({ e, all, director, locked, onChange }: { e: Employee; all: Employee[]; director: string; locked: boolean; onChange(p: Partial<Employee>): void }) {
  const manager = e.managerId ? all.find((m) => m.id === e.managerId) : undefined;
  const positions = department(e.department)?.positions ?? [];
  return (
    <tr>
      <td className="mono">{e.id}</td>
      <td style={{ minWidth: 190 }}>
        {locked ? (
          fullName(e)
        ) : (
          <div className="row" style={{ gap: 4, flexWrap: "nowrap" }}>
            <input aria-label="First name" className="input cell" style={{ width: 90 }} value={e.firstName} onChange={(ev) => onChange({ firstName: ev.target.value })} />
            <input aria-label="Last name" className="input cell" style={{ width: 120 }} value={e.lastName} onChange={(ev) => onChange({ lastName: ev.target.value })} />
          </div>
        )}
      </td>
      <td>
        {e.department}
        {e.isManager && <span className="badge badge-info" style={{ marginLeft: 6 }}>Manager</span>}
      </td>
      <td>
        {locked || e.isManager ? (
          e.position
        ) : (
          <select aria-label="Position" className="select input cell" value={e.position} onChange={(ev) => onChange({ position: ev.target.value })}>
            {positions.filter((p) => !p.manager).map((p) => (
              <option key={p.title}>{p.title}</option>
            ))}
          </select>
        )}
      </td>
      <td>
        {locked ? <span className="mono">{e.hireDate}</span> : <input aria-label="Hire date" type="date" className="input cell" value={e.hireDate} onChange={(ev) => ev.target.value && onChange({ hireDate: ev.target.value })} />}
      </td>
      <td>{e.contractType}</td>
      <td className="num">{e.hoursPerWeek}</td>
      <td className="num">
        {locked ? (
          e.startSalary.toLocaleString("en-GB")
        ) : (
          <input aria-label="Start salary" type="number" step={50} className="input cell num" style={{ width: 90, textAlign: "right" }} value={e.startSalary} onChange={(ev) => onChange({ startSalary: Math.round(Number(ev.target.value) || 0) })} />
        )}
      </td>
      <td className="small">{manager ? `${manager.id} ${fullName(manager)}` : (e.managerName ?? director)}</td>
      <td>
        {locked ? (
          "No"
        ) : (
          <label className="check" style={{ alignItems: "center" }}>
            <input type="checkbox" checked={e.leaves} disabled={e.isManager} onChange={(ev) => onChange({ leaves: ev.target.checked })} />
            <span className="small">{e.leaves ? "Yes" : "No"}</span>
          </label>
        )}
      </td>
    </tr>
  );
}
