/**
 * Check that every chart series stays distinguishable — including to viewers with colour-vision
 * deficiency.
 *
 *   node scripts/validate-palette.mjs
 *
 * The original macro triad was validated this way and the resulting figures written into a comment,
 * but the script itself was never kept. That is close to worthless: a claim of validation nobody can
 * re-run is just a claim, and it silently stops being true the moment a series is added or the
 * background changes. This exists so the check is repeatable — and it will be needed again for the
 * dark theme, where the same hues sit on a different ground.
 *
 * Method: simulate protanopia, deuteranopia and tritanopia with the Brettel/Viénot-style matrices
 * applied in linear RGB, then measure every pair with CIEDE2000. The worst pair across all four
 * views (normal + three deficiencies) is what decides the palette.
 */

const MIN_PAIR_DELTA = 15; // Below this two series start to read as the same colour.
const MIN_CONTRAST = 3.0; // WCAG non-text contrast, against the chart background.

const BACKGROUND = "#ffffff";

/**
 * Two palettes, because they are read differently.
 *
 * The macro triad appears in a *stacked* bar, where a reader only ever compares bands that touch.
 * Adjacent separation is therefore the right bar, and it is the one the original validation used.
 *
 * The overlay palette appears in the custom chart, where any two lines can be compared against each
 * other. Every pair must separate, which is a far harder constraint — and the reason the overlay is
 * capped at five series. A curated search showed six cannot clear ΔE 15 across all three deficiency
 * models without abandoning the app's colour register entirely.
 *
 * Colours are assigned to overlay slots *by selection order*, not by nutrient. That way the set
 * actually drawn is always this validated set, whichever nutrients the user happens to pick — a
 * fixed colour per nutrient would render an arbitrary, unvalidated subset.
 */
const STACKED = {
  // Order matters: these are checked as neighbours in the stack.
  protein_g: "#2c6fc4",
  carbs_g: "#c0722a",
  fat_g: "#6b4e8f",
};

const OVERLAY = {
  slot1: "#0e6e62",
  slot2: "#8b5cf6",
  slot3: "#8a7300",
  slot4: "#e0629a",
  slot5: "#0f172a",
};

// --- colour conversions ----------------------------------------------------

const hexToRgb = (hex) => {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
};

const toLinear = (c) => {
  const s = c / 255;
  return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
};

const fromLinear = (c) => {
  const s = c <= 0.0031308 ? c * 12.92 : 1.055 * c ** (1 / 2.4) - 0.055;
  return Math.max(0, Math.min(255, Math.round(s * 255)));
};

function rgbToLab([r, g, b]) {
  const [lr, lg, lb] = [toLinear(r), toLinear(g), toLinear(b)];
  // sRGB → XYZ (D65), then XYZ → Lab.
  let x = (lr * 0.4124 + lg * 0.3576 + lb * 0.1805) / 0.95047;
  let y = lr * 0.2126 + lg * 0.7152 + lb * 0.0722;
  let z = (lr * 0.0193 + lg * 0.1192 + lb * 0.9505) / 1.08883;
  const f = (t) => (t > 0.008856 ? Math.cbrt(t) : 7.787 * t + 16 / 116);
  [x, y, z] = [f(x), f(y), f(z)];
  return [116 * y - 16, 500 * (x - y), 200 * (y - z)];
}

/** CIEDE2000 — perceptual distance. Worth the algebra; plain Euclidean Lab misleads badly on blues. */
function deltaE2000(lab1, lab2) {
  const [L1, a1, b1] = lab1;
  const [L2, a2, b2] = lab2;
  const rad = Math.PI / 180;

  const avgL = (L1 + L2) / 2;
  const C1 = Math.hypot(a1, b1);
  const C2 = Math.hypot(a2, b2);
  const avgC = (C1 + C2) / 2;
  const G = 0.5 * (1 - Math.sqrt(avgC ** 7 / (avgC ** 7 + 25 ** 7)));

  const a1p = a1 * (1 + G);
  const a2p = a2 * (1 + G);
  const C1p = Math.hypot(a1p, b1);
  const C2p = Math.hypot(a2p, b2);
  const avgCp = (C1p + C2p) / 2;

  const h1p = (Math.atan2(b1, a1p) / rad + 360) % 360;
  const h2p = (Math.atan2(b2, a2p) / rad + 360) % 360;

  let dhp = h2p - h1p;
  if (Math.abs(dhp) > 180) dhp -= Math.sign(dhp) * 360;

  const dLp = L2 - L1;
  const dCp = C2p - C1p;
  const dHp = 2 * Math.sqrt(C1p * C2p) * Math.sin((dhp * rad) / 2);

  let avgHp = (h1p + h2p) / 2;
  if (Math.abs(h1p - h2p) > 180) avgHp += 180;
  if (avgHp >= 360) avgHp -= 360;

  const T =
    1 -
    0.17 * Math.cos((avgHp - 30) * rad) +
    0.24 * Math.cos(2 * avgHp * rad) +
    0.32 * Math.cos((3 * avgHp + 6) * rad) -
    0.2 * Math.cos((4 * avgHp - 63) * rad);

  const Sl = 1 + (0.015 * (avgL - 50) ** 2) / Math.sqrt(20 + (avgL - 50) ** 2);
  const Sc = 1 + 0.045 * avgCp;
  const Sh = 1 + 0.015 * avgCp * T;
  const Rt =
    -2 *
    Math.sqrt(avgCp ** 7 / (avgCp ** 7 + 25 ** 7)) *
    Math.sin(60 * Math.exp(-(((avgHp - 275) / 25) ** 2)) * rad);

  return Math.sqrt(
    (dLp / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2 + Rt * (dCp / Sc) * (dHp / Sh),
  );
}

// --- CVD simulation --------------------------------------------------------

/** Applied in linear RGB — simulating on gamma-encoded values overstates separation. */
const CVD_MATRICES = {
  protanopia: [0.152, 1.053, -0.205, 0.115, 0.786, 0.099, -0.004, -0.048, 1.052],
  deuteranopia: [0.367, 0.861, -0.228, 0.28, 0.673, 0.047, -0.012, 0.043, 0.969],
  tritanopia: [1.256, -0.077, -0.179, -0.078, 0.931, 0.148, 0.005, 0.691, 0.304],
};

function simulate(hex, kind) {
  if (kind === "normal") return hexToRgb(hex);
  const m = CVD_MATRICES[kind];
  const [r, g, b] = hexToRgb(hex).map(toLinear);
  return [
    fromLinear(m[0] * r + m[1] * g + m[2] * b),
    fromLinear(m[3] * r + m[4] * g + m[5] * b),
    fromLinear(m[6] * r + m[7] * g + m[8] * b),
  ];
}

const relativeLuminance = (hex) => {
  const [r, g, b] = hexToRgb(hex).map(toLinear);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};

function contrastRatio(a, b) {
  const [hi, lo] = [relativeLuminance(a), relativeLuminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

// --- the check -------------------------------------------------------------

const VIEWS = ["normal", "protanopia", "deuteranopia", "tritanopia"];
const failures = [];

const fmt = (p) => `${p.view.padEnd(13)} ${p.a} / ${p.b} — ΔE ${p.delta.toFixed(1)}`;

/** `mode: "all"` compares every pair; `"adjacent"` only neighbours, for stacked bands. */
function check(label, palette, mode) {
  const names = Object.keys(palette);
  let worst = { delta: Infinity, view: "-", a: "-", b: "-" };

  for (const view of VIEWS) {
    const labs = Object.fromEntries(
      names.map((name) => [name, rgbToLab(simulate(palette[name], view))]),
    );
    for (let i = 0; i < names.length; i++) {
      const limit = mode === "adjacent" ? Math.min(i + 2, names.length) : names.length;
      for (let j = i + 1; j < limit; j++) {
        const delta = deltaE2000(labs[names[i]], labs[names[j]]);
        const pair = { view, a: names[i], b: names[j], delta };
        if (delta < worst.delta) worst = pair;
        if (delta < MIN_PAIR_DELTA) failures.push(pair);
      }
    }
  }

  for (const name of names) {
    const ratio = contrastRatio(palette[name], BACKGROUND);
    if (ratio < MIN_CONTRAST) {
      failures.push({ view: "contrast", a: name, b: "background", delta: ratio });
    }
  }

  console.log(`${label}: ${names.length} series, ${mode} pairs`);
  console.log(`  worst: ${fmt(worst)}`);
}

console.log(`Background ${BACKGROUND}, ${VIEWS.length} vision models\n`);
check("Stacked macros", STACKED, "adjacent");
check("Overlay slots", OVERLAY, "all");

if (failures.length > 0) {
  console.error(`\n${failures.length} pair(s) below ΔE ${MIN_PAIR_DELTA} or ${MIN_CONTRAST}:1:`);
  for (const failure of failures) console.error(`  ${fmt(failure)}`);
  process.exit(1);
}

console.log(`\nAll checked pairs clear ΔE ${MIN_PAIR_DELTA}; all series clear ${MIN_CONTRAST}:1.`);
