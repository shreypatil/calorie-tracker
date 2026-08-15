import { nutrientUnit } from "../../lib/format";

/**
 * Chart tokens, shared so every chart reads as one system.
 *
 * The macro series colors were validated for colour-vision-deficiency
 * separation (worst adjacent pair ΔE 22.7 protan / 20.0 tritan) rather than
 * chosen by eye. Axes and grid are deliberately recessive: the data is the only
 * thing on the page with saturation.
 */

export const SERIES = {
  calories: "#0e6e62",
  protein_g: "#2c6fc4",
  carbs_g: "#c0722a",
  fat_g: "#6b4e8f",
  target: "#6a6e76",
} as const;

/**
 * Colours for the custom overlay chart, assigned **by selection order** rather than by nutrient.
 *
 * A fixed colour per nutrient sounds tidier but is unsafe: the user picks an arbitrary subset, and
 * an arbitrary subset of a large palette is not the set anyone validated. Assigning by slot means
 * whatever is drawn is always exactly these five, which `scripts/validate-palette.mjs` checks
 * all-pairs against protanopia, deuteranopia and tritanopia (worst ΔE 16.2).
 *
 * Five is the cap, and it is a real limit rather than a round number — six cannot clear the
 * threshold without leaving the app's colour register entirely.
 */
export const OVERLAY_SERIES = ["#0e6e62", "#8b5cf6", "#8a7300", "#e0629a", "#0f172a"] as const;

/** Redundant encoding: identity never rests on colour alone, so each slot also has a stroke. */
export const OVERLAY_DASHES = ["0", "7 3", "2 3", "11 4", "7 3 2 3"] as const;

export const MAX_OVERLAY_SERIES = OVERLAY_SERIES.length;

export const AXIS = {
  stroke: "#e3dfd7",
  tick: { fill: "#6a6e76", fontSize: 11, fontFamily: "IBM Plex Mono, monospace" },
};

export const GRID = { stroke: "#eeebe5", strokeDasharray: "0" } as const;

/** Charts leave room on the right so the last x-axis label is not clipped. */
export const CHART_MARGIN = { top: 8, right: 28, bottom: 4, left: 4 };

/**
 * Metrics sharing a unit share an axis.
 *
 * Overlaying calories (~2,000) with protein (~100) on one scale flattens protein onto the floor —
 * a chart that looks fine and says nothing. Grouping by unit is what lets the caller give each
 * family its own axis, and refuse a third rather than draw something misleading.
 */
export function unitFamilies(metrics: string[]): string[] {
  return [...new Set(metrics.map((metric) => nutrientUnit(metric)))];
}
