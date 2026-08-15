/** Display formatting. Kept in one place so numbers read the same everywhere. */

import type { Micronutrient } from "./types";

export function formatNumber(value: number | null | undefined, decimals = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

/** Grams and milligrams: show a decimal only when the value is small. */
export function formatAmount(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return formatNumber(value, value !== 0 && Math.abs(value) < 10 ? 1 : 0);
}

const NUTRIENT_LABELS: Record<string, string> = {
  calories: "Calories",
  protein_g: "Protein",
  carbs_g: "Carbs",
  fat_g: "Fat",
  fiber_g: "Fiber",
  sugar_g: "Sugar",
  sodium_mg: "Sodium",
  potassium_mg: "Potassium",
  calcium_mg: "Calcium",
  iron_mg: "Iron",
  cholesterol_mg: "Cholesterol",
  vitamin_a_mcg: "Vitamin A",
  vitamin_c_mg: "Vitamin C",
  vitamin_d_mcg: "Vitamin D",
  vitamin_b12_mcg: "Vitamin B12",
};

export function nutrientLabel(name: string): string {
  return NUTRIENT_LABELS[name] ?? name;
}

/** The unit is encoded in the field name — `sodium_mg` is milligrams. */
export function nutrientUnit(name: string): string {
  if (name === "calories") return "kcal";
  const suffix = name.split("_").pop();
  return suffix === "mcg" ? "µg" : (suffix ?? "");
}

export function formatNutrient(name: string, value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${formatAmount(value)} ${nutrientUnit(name)}`;
}

export const MICRO_LABELS = NUTRIENT_LABELS as Record<Micronutrient, string>;

/** Dates arrive as YYYY-MM-DD; parse as local so they don't shift a day. */
export function parseDate(value: string): Date {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day);
}

export function toISODate(date: Date): string {
  const month = `${date.getMonth() + 1}`.padStart(2, "0");
  const day = `${date.getDate()}`.padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

export function today(): string {
  return toISODate(new Date());
}

export function daysAgo(count: number): string {
  const date = new Date();
  date.setDate(date.getDate() - count);
  return toISODate(date);
}

export function formatDate(value: string): string {
  return parseDate(value).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export function formatDateShort(value: string): string {
  return parseDate(value).toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

export function formatDayLabel(value: string): string {
  const date = parseDate(value);
  const iso = toISODate(date);
  if (iso === today()) return "Today";
  if (iso === daysAgo(1)) return "Yesterday";
  return date.toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" });
}

export const MEAL_LABELS: Record<string, string> = {
  breakfast: "Breakfast",
  lunch: "Lunch",
  dinner: "Dinner",
  snack: "Snacks",
};
