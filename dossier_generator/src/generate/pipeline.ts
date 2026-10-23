import { extractJson } from "../ai/json";
import { personasPrompt, storylinePrompt, SYSTEM } from "../ai/prompts";
import type { ModelProvider } from "../ai/types";
import { ModelError } from "../ai/types";
import type { Correction, Employee, Storyline } from "../model/dossier";
import { createRng } from "../model/random";
import { LIMITS } from "./config";
import type { StorylinePlan } from "./normalize";
import { normalizePersonas, normalizeStoryline, planStoryline } from "./normalize";
import { offlinePersonasRaw, offlineStorylineRaw } from "./offline";
import type { GenerationConfig } from "./types";

/**
 * Steps 2 and 3, with any model. Each call returns what was asked, what came
 * back, and what code corrected, so the UI can show all three.
 */

export interface ModelExchange {
  label: string;
  prompt: string;
  answer: string;
}

export interface StepCallbacks {
  signal?: AbortSignal;
  onText?: (label: string, textSoFar: string) => void;
  onProgress?: (done: number, total: number) => void;
}

export interface PersonaStepResult {
  employees: Employee[];
  corrections: Correction[];
  exchanges: ModelExchange[];
  source: string;
}

export async function runPersonaStep(config: GenerationConfig, provider: ModelProvider, cb: StepCallbacks = {}): Promise<PersonaStepResult> {
  const rng = createRng(config.seed).fork("personas");
  const fill = (n: number) => offlinePersonasRaw(config, rng.fork("fill"), n);
  if (provider.id === "offline") {
    const { employees, corrections } = normalizePersonas(offlinePersonasRaw(config, rng), config, rng, fill);
    return { employees, corrections, exchanges: [], source: provider.describe() };
  }
  if (config.employeeCount > LIMITS.maxEmployeesWithAi) {
    throw new ModelError(`With a model, the demo makes at most ${LIMITS.maxEmployeesWithAi} employees per run. Lower the number, or use "No AI" for large volumes.`, "refused");
  }
  const prompt = personasPrompt(config);
  const label = "Personas";
  const answer = await provider.complete({
    system: SYSTEM,
    prompt,
    signal: cb.signal,
    maxTokens: 300 + config.employeeCount * 120,
    onText: (t) => cb.onText?.(label, t),
  });
  let raw: unknown;
  try {
    raw = extractJson(answer);
  } catch {
    throw new ModelError("The model's answer was not valid JSON. Try again, or try another model.", "retry");
  }
  const { employees, corrections } = normalizePersonas(raw, config, rng, fill);
  return { employees, corrections, exchanges: [{ label, prompt, answer }], source: provider.describe() };
}

export interface StorylineStepResult {
  storylines: Record<string, Storyline>;
  corrections: Correction[];
  exchanges: ModelExchange[];
  source: string;
}

export async function runStorylineStep(
  config: GenerationConfig,
  employees: Employee[],
  provider: ModelProvider,
  cb: StepCallbacks = {},
): Promise<StorylineStepResult> {
  const rng = createRng(config.seed).fork("storylines");
  const forks = new Map(employees.map((e) => [e.id, rng.fork(e.id)]));
  const plans: StorylinePlan[] = employees.map((e) => planStoryline(e, config, forks.get(e.id)!));
  const storylines: Record<string, Storyline> = {};
  const corrections: Correction[] = [];
  const exchanges: ModelExchange[] = [];

  if (provider.id === "offline") {
    for (const plan of plans) {
      const r = forks.get(plan.employee.id)!;
      const result = normalizeStoryline(offlineStorylineRaw(plan, config, r), plan, config, r);
      storylines[plan.employee.id] = result.storyline;
      corrections.push(...result.corrections);
    }
    return { storylines, corrections, exchanges, source: provider.describe() };
  }

  const batches: StorylinePlan[][] = [];
  for (let i = 0; i < plans.length; i += LIMITS.storylineBatchSize) batches.push(plans.slice(i, i + LIMITS.storylineBatchSize));

  let done = 0;
  cb.onProgress?.(0, plans.length);
  for (const [index, batch] of batches.entries()) {
    const label = `Storylines ${index + 1}/${batches.length}`;
    const prompt = storylinePrompt(config, batch, employees);
    const answer = await provider.complete({
      system: SYSTEM,
      prompt,
      signal: cb.signal,
      maxTokens: 800 + batch.length * 2000,
      onText: (t) => cb.onText?.(label, t),
    });
    exchanges.push({ label, prompt, answer });
    let list: unknown[] = [];
    try {
      const parsed = extractJson(answer) as { storylines?: unknown[] } | unknown[];
      list = Array.isArray(parsed) ? parsed : (parsed.storylines ?? []);
    } catch {
      corrections.push({ step: "storylines", message: `${label}: the answer was not valid JSON; code filled in the basics for ${batch.length} employees.` });
    }
    for (const plan of batch) {
      const e = plan.employee;
      const raw = list.find((x) => String((x as { employeeId?: unknown })?.employeeId) === e.id);
      if (!raw) corrections.push({ step: "storylines", employeeId: e.id, message: `No storyline came back for ${e.id}; code filled in the basics.` });
      const r = forks.get(e.id)!;
      const result = normalizeStoryline(raw ?? {}, plan, config, r);
      storylines[e.id] = result.storyline;
      corrections.push(...result.corrections);
      done++;
    }
    cb.onProgress?.(done, plans.length);
  }
  return { storylines, corrections, exchanges, source: provider.describe() };
}
