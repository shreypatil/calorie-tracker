/**
 * The meal entry form (FR-2).
 *
 * Micronutrients are collapsed by default: they matter, but requiring eleven
 * fields to log a bowl of oatmeal would stop anyone logging anything.
 */

import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { ScanControl } from "../components/photo/ScanControl";
import { Alert, Button, Card, CardHeader, Field, Input, Select } from "../components/ui";
import { useCreateEntry, useEstimateNutrition } from "../lib/queries";
import { ApiError } from "../lib/api";
import { MEAL_LABELS, nutrientLabel, nutrientUnit, today } from "../lib/format";
import {
  ESTIMABLE_FIELDS,
  MEAL_TYPES,
  MICRONUTRIENTS,
  type DraftRow,
  type EstimableField,
  type FieldSource,
  type MealType,
  type Micronutrient,
} from "../lib/types";

const optionalAmount = z
  .union([z.literal(""), z.coerce.number().min(0, "Cannot be negative")])
  .transform((value) => (value === "" ? undefined : value))
  .optional();

// Built by reduce rather than Object.fromEntries so the key names survive into
// the inferred type — otherwise every micronutrient field is untyped.
const microFields = MICRONUTRIENTS.reduce(
  (fields, name) => ({ ...fields, [name]: optionalAmount }),
  {} as Record<Micronutrient, typeof optionalAmount>,
);

const schema = z.object({
  consumed_on: z.string().min(1, "Pick a date"),
  meal_type: z.enum(["breakfast", "lunch", "dinner", "snack"]),
  food_name: z.string().trim().min(1, "Give the food a name").max(200),
  quantity: z.coerce.number().gt(0, "Must be more than zero"),
  unit: z.string().trim().min(1).max(30),
  calories: z.coerce.number().min(0, "Cannot be negative"),
  protein_g: z.coerce.number().min(0, "Cannot be negative"),
  carbs_g: z.coerce.number().min(0, "Cannot be negative"),
  fat_g: z.coerce.number().min(0, "Cannot be negative"),
  ...microFields,
});

type FormValues = z.input<typeof schema>;

// Every micronutrient is listed explicitly. `reset()` only touches fields the object names, so
// omitting them left them populated after Clear, after saving, and after a photo scan — one
// missing set of keys causing three separate bugs.
const DEFAULTS = {
  consumed_on: today(),
  meal_type: "breakfast",
  food_name: "",
  quantity: 1,
  unit: "serving",
  calories: 0,
  protein_g: 0,
  carbs_g: 0,
  fat_g: 0,
  ...Object.fromEntries(MICRONUTRIENTS.map((name) => [name, ""])),
} as unknown as FormValues;

/** Marks a field whose value a model produced, so a guess never passes for a measurement. */
function estimatedLabel(base: string, estimated: boolean): string {
  return estimated ? `${base}  \u2726 estimated` : base;
}

export function LogEntryForm({ onLogged }: { onLogged?: () => void }) {
  const create = useCreateEntry();
  const [showMicros, setShowMicros] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const [scanNote, setScanNote] = useState<string | null>(null);

  const estimate = useEstimateNutrition();

  /**
   * Where each field's current value came from.
   *
   * Three things can now fill a field and an estimate may only touch some of them. `dirtyFields`
   * alone is not enough: a photo scan fills the form through `reset()`, which *clears* dirty state,
   * so scanned values would look untouched and get overwritten. Tracking the source explicitly is
   * the only way to tell "the user left this alone" from "something already filled it".
   */
  const [source, setSource] = useState<Partial<Record<string, FieldSource>>>({});

  /** Values as they were before the last estimate, so it can be undone. */
  const [beforeEstimate, setBeforeEstimate] = useState<Record<string, unknown> | null>(null);

  const {
    register,
    handleSubmit,
    reset,
    control,
    getValues,
    setValue,
    formState: { errors, dirtyFields },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: DEFAULTS,
  });

  // The scan is filed against whatever date and meal the form currently shows, so a photo
  // taken for yesterday's lunch does not silently land on today's breakfast.
  const consumedOn = useWatch({ control, name: "consumed_on" }) as string;
  const mealType = useWatch({ control, name: "meal_type" }) as MealType;
  const foodName = useWatch({ control, name: "food_name" }) as string;

  /** One food read from a photo: fill the form rather than making the user retype it. */
  function applyScannedRow(row: DraftRow) {
    const entry = row.entry;
    if (!entry) return;

    reset({
      ...DEFAULTS,
      consumed_on: entry.consumed_on,
      meal_type: entry.meal_type,
      food_name: entry.food_name,
      quantity: entry.quantity,
      unit: entry.unit,
      calories: entry.calories,
      protein_g: entry.protein_g,
      carbs_g: entry.carbs_g,
      fat_g: entry.fat_g,
      ...Object.fromEntries(
        MICRONUTRIENTS.map((name) => [name, entry[name] ?? ""]).filter(([, value]) => value !== ""),
      ),
    } as unknown as FormValues);

    // Anything the reading could not stand behind is said out loud — a blank field with no
    // explanation would look like the label simply did not list it.
    setScanNote(
      row.issues.length > 0
        ? row.issues.map((issue) => issue.message).join(" ")
        : "Filled in from the photo — check it before saving.",
    );
    // Marked so a later estimate treats them as already filled rather than as untouched.
    setSource(
      Object.fromEntries(
        ["calories", "protein_g", "carbs_g", "fat_g", ...MICRONUTRIENTS]
          .filter((name) => (entry as unknown as Record<string, unknown>)[name] != null)
          .map((name) => [name, "photo" as const]),
      ),
    );
    setBeforeEstimate(null);
    setShowMicros(MICRONUTRIENTS.some((name) => entry[name] != null));
  }

  const estimatedCount = Object.values(source).filter((origin) => origin === "estimate").length;

  /** A field may be estimated unless the user typed it or a photo filled it. */
  function isEligible(field: EstimableField): boolean {
    if (dirtyFields[field as keyof FormValues]) return false;
    const origin = source[field];
    // "estimate" is eligible so pressing the button again refreshes rather than freezing the
    // first answer; anything else present was put there deliberately.
    return origin === undefined || origin === "estimate";
  }

  async function runEstimate() {
    const values = getValues();
    const wanted = ESTIMABLE_FIELDS.filter(isEligible);
    if (wanted.length === 0) return;

    // Everything the user already provided travels as an anchor, so the estimate is scaled to
    // their portion and their figures rather than to a generic serving.
    const known: Partial<Record<EstimableField, number>> = {};
    for (const field of ESTIMABLE_FIELDS) {
      const raw = values[field as keyof FormValues];
      if (!isEligible(field) && raw !== "" && raw != null) known[field] = Number(raw);
    }

    setServerError(null);
    const previous: Record<string, unknown> = {};
    for (const field of wanted) previous[field] = values[field as keyof FormValues];

    try {
      const result = await estimate.mutateAsync({
        food_name: String(values.food_name ?? "").trim(),
        quantity: values.quantity ? Number(values.quantity) : null,
        unit: values.unit ? String(values.unit) : null,
        known,
        fields: wanted,
      });

      const filled = Object.entries(result.values) as [EstimableField, number][];
      for (const [field, value] of filled) {
        // shouldDirty stays false: an estimated value is not a user edit, so a second press
        // can refresh it.
        setValue(field as keyof FormValues, value as never, { shouldDirty: false });
      }
      setBeforeEstimate(previous);
      setSource((current) => ({
        ...current,
        ...Object.fromEntries(filled.map(([field]) => [field, "estimate" as const])),
      }));
      if (filled.some(([field]) => MICRONUTRIENTS.includes(field as Micronutrient))) {
        setShowMicros(true);
      }
      setScanNote(null);
    } catch (error) {
      setServerError(
        error instanceof ApiError ? error.message : "Could not estimate that. Try again.",
      );
    }
  }

  function undoEstimate() {
    if (!beforeEstimate) return;
    for (const [field, value] of Object.entries(beforeEstimate)) {
      setValue(field as keyof FormValues, value as never, { shouldDirty: false });
    }
    setSource((current) =>
      Object.fromEntries(Object.entries(current).filter(([, origin]) => origin !== "estimate")),
    );
    setBeforeEstimate(null);
  }

  async function onSubmit(values: FormValues) {
    setServerError(null);
    try {
      const parsed = schema.parse(values);
      // Drop unfilled micronutrients so they stay null rather than becoming zero,
      // which would claim the food genuinely contains none.
      const body = Object.fromEntries(
        Object.entries(parsed).filter(([, value]) => value !== undefined),
      );
      await create.mutateAsync(body);
      reset({ ...DEFAULTS, consumed_on: values.consumed_on, meal_type: values.meal_type });
      setShowMicros(false);
      setScanNote(null);
      setSource({});
      setBeforeEstimate(null);
      onLogged?.();
    } catch (error) {
      setServerError(
        error instanceof ApiError
          ? error.problem?.errors?.[0]?.message
            ? `${error.problem.errors[0].field}: ${error.problem.errors[0].message}`
            : error.message
          : "Could not save the entry. Try again.",
      );
    }
  }

  return (
    <Card>
      <CardHeader title="Log a meal" subtitle="Nutrition values are per the quantity you enter." />

      <ScanControl
        mealType={mealType}
        consumedOn={consumedOn}
        onSingleResult={applyScannedRow}
        onCommitted={() => onLogged?.()}
      />

      <form onSubmit={handleSubmit(onSubmit)} className="p-5">
        {serverError && (
          <div className="mb-4">
            <Alert>{serverError}</Alert>
          </div>
        )}

        {scanNote && (
          <div className="mb-4">
            <Alert tone="info">{scanNote}</Alert>
          </div>
        )}

        {estimatedCount > 0 && (
          <div className="mb-4 flex flex-wrap items-center gap-3 rounded border border-rule bg-paper px-3 py-2">
            <span className="text-[13px] text-ink-soft">
              ✦ {estimatedCount} {estimatedCount === 1 ? "field" : "fields"} estimated by AI — check
              them before saving.
            </span>
            <button
              type="button"
              className="text-[13px] text-accent underline"
              onClick={undoEstimate}
            >
              Undo estimate
            </button>
          </div>
        )}

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="Date" error={errors.consumed_on?.message}>
            <Input type="date" max={today()} {...register("consumed_on")} />
          </Field>
          <Field label="Meal" error={errors.meal_type?.message}>
            <Select {...register("meal_type")}>
              {MEAL_TYPES.map((meal) => (
                <option key={meal} value={meal}>
                  {MEAL_LABELS[meal]}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Food" error={errors.food_name?.message} className="sm:col-span-2">
            <div className="flex gap-2">
              <Input placeholder="Oatmeal with banana" {...register("food_name")} />
              <Button
                type="button"
                className="whitespace-nowrap"
                disabled={estimate.isPending || !foodName?.trim()}
                onClick={runEstimate}
              >
                {estimate.isPending ? "Estimating…" : "Estimate nutrition"}
              </Button>
            </div>
          </Field>

          <Field label="Quantity" error={errors.quantity?.message}>
            <Input type="number" step="any" min="0" {...register("quantity")} />
          </Field>
          <Field label="Unit" error={errors.unit?.message}>
            <Input placeholder="bowl" {...register("unit")} />
          </Field>
          <Field
            label={estimatedLabel("Calories (kcal)", source.calories === "estimate")}
            error={errors.calories?.message}
          >
            <Input type="number" step="any" min="0" {...register("calories")} />
          </Field>
          <Field
            label={estimatedLabel("Protein (g)", source.protein_g === "estimate")}
            error={errors.protein_g?.message}
          >
            <Input type="number" step="any" min="0" {...register("protein_g")} />
          </Field>
          <Field
            label={estimatedLabel("Carbs (g)", source.carbs_g === "estimate")}
            error={errors.carbs_g?.message}
          >
            <Input type="number" step="any" min="0" {...register("carbs_g")} />
          </Field>
          <Field
            label={estimatedLabel("Fat (g)", source.fat_g === "estimate")}
            error={errors.fat_g?.message}
          >
            <Input type="number" step="any" min="0" {...register("fat_g")} />
          </Field>
        </div>

        <div className="mt-5 border-t border-rule pt-4">
          <button
            type="button"
            className="text-[13px] text-accent underline"
            aria-expanded={showMicros}
            onClick={() => setShowMicros((open) => !open)}
          >
            {showMicros ? "Hide micronutrients" : "Add micronutrients (optional)"}
          </button>

          {showMicros && (
            <div className="mt-4 grid gap-4 sm:grid-cols-3 lg:grid-cols-4">
              {MICRONUTRIENTS.map((name) => (
                <Field
                  key={name}
                  label={estimatedLabel(
                    `${nutrientLabel(name)} (${nutrientUnit(name)})`,
                    source[name] === "estimate",
                  )}
                  error={errors[name]?.message as string | undefined}
                >
                  <Input type="number" step="any" min="0" placeholder="—" {...register(name)} />
                </Field>
              ))}
            </div>
          )}
        </div>

        <div className="mt-5 flex justify-end gap-2">
          <Button
            type="button"
            onClick={() => {
              reset(DEFAULTS);
              setShowMicros(false);
              setScanNote(null);
              setSource({});
              setBeforeEstimate(null);
            }}
          >
            Clear
          </Button>
          <Button type="submit" variant="primary" disabled={create.isPending}>
            {create.isPending ? "Saving…" : "Save entry"}
          </Button>
        </div>
      </form>
    </Card>
  );
}
