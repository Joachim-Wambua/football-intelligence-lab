import type { Pass } from "./contracts";

export type PassFilter = "all" | "completed" | "unsuccessful" | "progressive";

/** Presentation-only predicates over Python's flags, never recomputed geometry. */
export function filterPasses(passes: Pass[], filter: PassFilter): Pass[] {
  switch (filter) {
    case "completed": return passes.filter(pass => pass.completed);
    case "unsuccessful": return passes.filter(pass => !pass.completed);
    case "progressive": return passes.filter(pass => pass.progressive);
    default: return passes;
  }
}
