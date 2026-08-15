/** Shapes returned by the API. Mirrors the backend response schemas. */

export type MealType = "breakfast" | "lunch" | "dinner" | "snack";
export type EntrySource = "manual" | "photo" | "chat" | "pdf";
export type Granularity = "day" | "week" | "month";

export const MEAL_TYPES: MealType[] = ["breakfast", "lunch", "dinner", "snack"];

export const MACROS = ["protein_g", "carbs_g", "fat_g"] as const;

/** The figures a draft row exposes as editable columns. */
export const DRAFT_MACROS = ["calories", ...MACROS] as const;
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

// --- Import (FR-8) --------------------------------------------------------

export type DateFormat = "DMY" | "MDY" | "YMD" | "ISO";
export type NutritionBasis = "per_serving" | "per_100g";
export type RowStatus = "ok" | "needs_review" | "invalid";
export type SourceKind = "table" | "prose";

export const DATE_FORMAT_LABELS: Record<DateFormat, string> = {
  DMY: "Day first (31/12/2026)",
  MDY: "Month first (12/31/2026)",
  YMD: "Year first (2026/12/31)",
  ISO: "ISO (2026-12-31)",
};

export interface ColumnMapping {
  source: string;
  target: string;
  confidence: number;
}

export interface TableMapping {
  columns: ColumnMapping[];
  date_format: DateFormat;
  basis: NutritionBasis;
  quantity_column: string | null;
  default_meal_type: MealType | null;
  header_row_index: number;
  notes: string;
}

export interface RowIssue {
  field: string | null;
  message: string;
}

export interface DraftRow {
  index: number;
  status: RowStatus;
  issues: RowIssue[];
  entry: FoodEntry | null;
  raw: Record<string, string>;
  duplicate_of: string | null;
}

export interface ImportSummary {
  filename: string;
  page_count: number;
  row_count: number;
  ready: number;
  needs_review: number;
  invalid: number;
  duplicates: number;
}

export interface PdfImportPreview {
  summary: ImportSummary;
  mapping: TableMapping;
  source_kind: SourceKind;
  rows: DraftRow[];
}

export interface ImportBatch {
  id: string;
  filename: string;
  row_count: number;
  created_at: string;
  entries_remaining: number;
}

// --- Chat (FR-6) ----------------------------------------------------------

export type ChatRole = "user" | "assistant" | "tool";
export type ActionStatus = "pending" | "confirmed" | "discarded";

/**
 * A change the assistant proposed. Nothing is written until it is confirmed, so
 * `arguments` is both the draft the user reviews and, once edited, exactly what
 * gets executed.
 */
export interface PendingAction {
  id: string;
  tool: string;
  summary: string;
  arguments: Record<string, unknown>;
  status: ActionStatus;
  result: Record<string, unknown> | null;
}

/** One row of a draft `log_meal` action, as carried in its arguments. */
export interface DraftMealItem {
  food_name: string;
  meal_type: MealType;
  consumed_on?: string | null;
  quantity: number;
  unit: string;
  calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  /** Micronutrients the assistant supplied ride along and stay editable. */
  [field: string]: unknown;
}

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  actions: PendingAction[];
  tool_name: string | null;
  created_at: string;
}

export interface ChatTurn {
  messages: ChatMessage[];
}

// --- Photo extraction (FR-5) ---------------------------------------------

export type PhotoKind = "label" | "meal";

/**
 * The result of reading one photo. Nothing here has been saved — rows are
 * always `needs_review`, whether transcribed from a label or estimated.
 */
export interface PhotoDraft {
  kind: PhotoKind;
  source_filename: string;
  basis: NutritionBasis;
  serving_size_g: number | null;
  confidence: number;
  notes: string;
  rows: DraftRow[];
}

/** One row per group: the dimension values, then the metric totals. */
export interface AggregateResponse {
  group_by: string[];
  metrics: string[];
  rows: Record<string, string | number>[];
}
