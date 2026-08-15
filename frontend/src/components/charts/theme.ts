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

export const AXIS = {
  stroke: "#e3dfd7",
  tick: { fill: "#6a6e76", fontSize: 11, fontFamily: "IBM Plex Mono, monospace" },
};

export const GRID = { stroke: "#eeebe5", strokeDasharray: "0" } as const;

/** Charts leave room on the right so the last x-axis label is not clipped. */
export const CHART_MARGIN = { top: 8, right: 28, bottom: 4, left: 4 };
