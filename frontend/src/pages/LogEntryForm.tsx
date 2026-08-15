/**
 * The meal entry form (FR-2).
 *
 * Micronutrients are collapsed by default: they matter, but requiring eleven
 * fields to log a bowl of oatmeal would stop anyone logging anything.
 */

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Alert, Button, Card, CardHeader, Field, Input, Select } from "../components/ui";
import { useCreateEntry } from "../lib/queries";
import { ApiError } from "../lib/api";
import { MEAL_LABELS, nutrientLabel, nutrientUnit, today } from "../lib/format";
import { MEAL_TYPES, MICRONUTRIENTS, type Micronutrient } from "../lib/types";

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
} as unknown as FormValues;

export function LogEntryForm({ onLogged }: { onLogged?: () => void }) {
  const create = useCreateEntry();
  const [showMicros, setShowMicros] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: DEFAULTS,
  });

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

      <form onSubmit={handleSubmit(onSubmit)} className="p-5">
        {serverError && (
          <div className="mb-4">
            <Alert>{serverError}</Alert>
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
            <Input placeholder="Oatmeal with banana" {...register("food_name")} />
          </Field>

          <Field label="Quantity" error={errors.quantity?.message}>
            <Input type="number" step="any" min="0" {...register("quantity")} />
          </Field>
          <Field label="Unit" error={errors.unit?.message}>
            <Input placeholder="bowl" {...register("unit")} />
          </Field>
          <Field label="Calories (kcal)" error={errors.calories?.message}>
            <Input type="number" step="any" min="0" {...register("calories")} />
          </Field>
          <Field label="Protein (g)" error={errors.protein_g?.message}>
            <Input type="number" step="any" min="0" {...register("protein_g")} />
          </Field>
          <Field label="Carbs (g)" error={errors.carbs_g?.message}>
            <Input type="number" step="any" min="0" {...register("carbs_g")} />
          </Field>
          <Field label="Fat (g)" error={errors.fat_g?.message}>
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
                  label={`${nutrientLabel(name)} (${nutrientUnit(name)})`}
                  error={errors[name]?.message as string | undefined}
                >
                  <Input type="number" step="any" min="0" placeholder="—" {...register(name)} />
                </Field>
              ))}
            </div>
          )}
        </div>

        <div className="mt-5 flex justify-end gap-2">
          <Button type="button" onClick={() => reset(DEFAULTS)}>
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
