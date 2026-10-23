/**
 * Seeded random numbers, so the same seed always produces the same dossier.
 * That makes a generated dataset reproducible: share the seed and the config,
 * and a teammate gets byte-for-byte the same import package (in "No AI" mode).
 */

export interface Rng {
  /** Float in [0, 1). */
  next(): number;
  int(min: number, maxInclusive: number): number;
  pick<T>(items: readonly T[]): T;
  chance(probability: number): boolean;
  shuffle<T>(items: readonly T[]): T[];
  /** A child generator that does not disturb this one's sequence. */
  fork(label: string): Rng;
}

function hashString(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

export function createRng(seed: number | string): Rng {
  let state = typeof seed === "number" ? seed >>> 0 : hashString(seed);
  if (state === 0) state = 0x9e3779b9;

  // mulberry32
  const next = () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };

  const rng: Rng = {
    next,
    int(min, maxInclusive) {
      return min + Math.floor(next() * (maxInclusive - min + 1));
    },
    pick(items) {
      if (items.length === 0) throw new Error("pick() from an empty list");
      return items[Math.floor(next() * items.length)];
    },
    chance(p) {
      return next() < p;
    },
    shuffle(items) {
      const a = [...items];
      for (let i = a.length - 1; i > 0; i--) {
        const j = Math.floor(next() * (i + 1));
        [a[i], a[j]] = [a[j], a[i]];
      }
      return a;
    },
    fork(label) {
      return createRng((hashString(label) ^ Math.floor(next() * 4294967296)) >>> 0);
    },
  };
  return rng;
}
