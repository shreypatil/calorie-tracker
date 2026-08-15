/** Shapes returned by the API. Mirrors the backend response schemas. */

export type MealType = "breakfast" | "lunch" | "dinner" | "snack";
export type EntrySource = "manual" | "photo" | "chat" | "pdf";
export type Granularity = "day" | "week" | "month";

export const MEAL_TYPES: MealType[] = ["breakfast", "lunch", "dinner", "snack"];

export const MACROS = ["protein_g", "carbs_g", "fat_g"] as const;
export type Macro = (typeof MACROS)[number];

export const MICRONUTRIENTS = [
  "fiber_g",
  "sugar_g",
  "sodium_mg",
  "potassium_mg",
  "calcium_mg",
  "iron_mg",
  "cholesterol_mg",
  "vitamin_a_mcg",
  "vitamin_c_mg",
  "vitamin_d_mcg",
  "vitamin_b12_mcg",
] as const;
export type Micronutrient = (typeof MICRONUTRIENTS)[number];

export interface Page<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
  has_next: boolean;
}

export interface User {
  id: string;
  email: string;
  display_name: string;
  created_at: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export type Micros = Partial<Record<Micronutrient, number | null>>;

export interface FoodEntry extends Micros {
  id: string;
  consumed_on: string;
  consumed_at: string | null;
  meal_type: MealType;
  food_name: string;
  quantity: number;
  unit: string;
  calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  micros_extra: Record<string, number> | null;
  source: EntrySource;
  source_ref: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface Goal {
  id: string;
  effective_from: string;
  calorie_target: number | null;
  protein_g: number | null;
  carbs_g: number | null;
  fat_g: number | null;
  weight_target_kg: number | null;
  micro_targets: Record<string, number> | null;
  created_at: string;
  updated_at: string;
}

export interface WeightLog {
  id: string;
  logged_on: string;
  weight_kg: number;
  created_at: string;
}

export interface MealTotals {
  meal_type: MealType;
  calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  entry_count: number;
}

export interface DailySummary {
  date: string;
  totals: Record<string, number>;
  by_meal: MealTotals[];
  goal: Goal | null;
  remaining_calories: number | null;
}

export interface TrendPoint {
  bucket: string;
  calories: number;
  entry_count: number;
}

export interface TrendResponse {
  granularity: Granularity;
  date_from: string;
  date_to: string;
  points: TrendPoint[];
}

export interface MacroPoint {
  bucket: string;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
}

export interface MacroBreakdown {
  granularity: Granularity;
  date_from: string;
  date_to: string;
  points: MacroPoint[];
  totals: Record<Macro, number>;
  share_of_calories: Record<Macro, number>;
}

export interface MicronutrientRow {
  name: string;
  total: number;
  daily_average: number;
  target: number | null;
}

export interface MicroSummary {
  date_from: string;
  date_to: string;
  days: number;
  nutrients: MicronutrientRow[];
}

export interface GoalComparisonPoint {
  bucket: string;
  days: number;
  actual: Record<string, number>;
  target: Record<string, number | null>;
}

export interface GoalVsActual {
  granularity: Granularity;
  date_from: string;
  date_to: string;
  points: GoalComparisonPoint[];
}
