/**
 * Goals and weight (FR-1).
 *
 * Goals are versioned, so the UI is explicit that saving creates a version
 * taking effect from a date — past days keep being measured against what was
 * actually set at the time.
 */

import { useState } from "react";
import { PageHeading } from "../components/Layout";
import {
  Alert,
  Button,
  Card,
  CardHeader,
  EmptyState,
  ErrorNote,
  Field,
  Input,
  Loading,
  Value,
} from "../components/ui";
import {
  useCurrentGoal,
  useDeleteGoal,
  useGoals,
  useRecordWeight,
  useSaveGoal,
  useWeights,
} from "../lib/queries";
import { ApiError } from "../lib/api";
import { formatAmount, formatDate, formatNumber, nutrientLabel, nutrientUnit, today } from "../lib/format";
import { MICRONUTRIENTS, type Goal } from "../lib/types";

type TargetForm = Record<string, string>;

const CORE_FIELDS = [
  { name: "calorie_target", label: "Calories (kcal)" },
  { name: "protein_g", label: "Protein (g)" },
  { name: "carbs_g", label: "Carbs (g)" },
  { name: "fat_g", label: "Fat (g)" },
  { name: "weight_target_kg", label: "Target weight (kg)" },
];

function toForm(goal: Goal | null | undefined): TargetForm {
  const values: TargetForm = { effective_from: today() };
  for (const field of CORE_FIELDS) {
    const value = goal?.[field.name as keyof Goal];
    values[field.name] = value === null || value === undefined ? "" : String(value);
  }
  for (const micro of MICRONUTRIENTS) {
    const value = goal?.micro_targets?.[micro];
    values[micro] = value === undefined ? "" : String(value);
  }
  return values;
}

export function Goals() {
  const current = useCurrentGoal();
  const history = useGoals();
  const save = useSaveGoal();
  const removeGoal = useDeleteGoal();

  const [form, setForm] = useState<TargetForm | null>(null);
  const [showMicros, setShowMicros] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  // Seed the form from the active goal once it has loaded.
  const values = form ?? toForm(current.data);
  const set = (key: string) => (event: React.ChangeEvent<HTMLInputElement>) => {
    setSaved(false);
    setForm({ ...values, [key]: event.target.value });
  };

  const numberOrNull = (raw: string) => (raw.trim() === "" ? null : Number(raw));

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setSaved(false);

    const microTargets: Record<string, number> = {};
    for (const micro of MICRONUTRIENTS) {
      const value = numberOrNull(values[micro] ?? "");
      if (value !== null) microTargets[micro] = value;
    }

    try {
      await save.mutateAsync({
        effective_from: values.effective_from,
        ...Object.fromEntries(
          CORE_FIELDS.map((field) => [field.name, numberOrNull(values[field.name] ?? "")]),
        ),
        micro_targets: Object.keys(microTargets).length ? microTargets : null,
      });
      setSaved(true);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? (err.problem?.errors?.[0]?.message ?? err.message)
          : "Could not save the goal. Try again.",
      );
    }
  }

  if (current.isLoading) return <Loading />;

  return (
    <>
      <PageHeading
        title="Goals"
        description="Targets are versioned: saving records what applies from a date onward, so past days keep their original targets."
      />

      <div className="grid gap-5 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Card>
            <CardHeader
              title="Set targets"
              subtitle="Leave a field blank to leave that target unset."
            />
            <form onSubmit={handleSubmit} className="p-5">
              {error && (
                <div className="mb-4">
                  <Alert>{error}</Alert>
                </div>
              )}
              {saved && (
                <div className="mb-4">
                  <Alert tone="info">Targets saved.</Alert>
                </div>
              )}

              <Field label="In effect from" className="mb-4 max-w-xs">
                <Input
                  type="date"
                  value={values.effective_from}
                  onChange={set("effective_from")}
                />
              </Field>

              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {CORE_FIELDS.map((field) => (
                  <Field key={field.name} label={field.label}>
                    <Input
                      type="number"
                      step="any"
                      min="0"
                      placeholder="—"
                      value={values[field.name] ?? ""}
                      onChange={set(field.name)}
                    />
                  </Field>
                ))}
              </div>

              <div className="mt-5 border-t border-rule pt-4">
                <button
                  type="button"
                  className="text-[13px] text-accent underline"
                  aria-expanded={showMicros}
                  onClick={() => setShowMicros((open) => !open)}
                >
                  {showMicros ? "Hide micronutrient targets" : "Set micronutrient targets"}
                </button>

                {showMicros && (
                  <div className="mt-4 grid gap-4 sm:grid-cols-3 lg:grid-cols-4">
                    {MICRONUTRIENTS.map((micro) => (
                      <Field
                        key={micro}
                        label={`${nutrientLabel(micro)} (${nutrientUnit(micro)})`}
                      >
                        <Input
                          type="number"
                          step="any"
                          min="0"
                          placeholder="—"
                          value={values[micro] ?? ""}
                          onChange={set(micro)}
                        />
                      </Field>
                    ))}
                  </div>
                )}
              </div>

              <div className="mt-5 flex justify-end">
                <Button type="submit" variant="primary" disabled={save.isPending}>
                  {save.isPending ? "Saving…" : "Save targets"}
                </Button>
              </div>
            </form>
          </Card>
        </div>

        <WeightPanel />
      </div>

      <div className="mt-5">
        <Card>
          <CardHeader title="Goal history" subtitle="Newest version first." />
          {history.isLoading ? (
            <Loading />
          ) : history.error ? (
            <ErrorNote error={history.error} />
          ) : history.data?.items.length === 0 ? (
            <EmptyState
              title="No goals yet"
              description="Save your targets above to start tracking against them."
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[40rem] border-collapse text-[13px]">
                <thead>
                  <tr className="border-b border-rule">
                    <th className="eyebrow px-5 py-2 text-left font-normal">In effect from</th>
                    <th className="eyebrow px-3 py-2 text-right font-normal">Calories</th>
                    <th className="eyebrow px-3 py-2 text-right font-normal">Protein</th>
                    <th className="eyebrow px-3 py-2 text-right font-normal">Carbs</th>
                    <th className="eyebrow px-3 py-2 text-right font-normal">Fat</th>
                    <th className="eyebrow px-3 py-2 text-right font-normal">Weight</th>
                    <th className="px-5 py-2" />
                  </tr>
                </thead>
                <tbody>
                  {history.data!.items.map((goal, index) => (
                    <tr key={goal.id} className="border-b border-rule-soft last:border-0">
                      <td className="whitespace-nowrap px-5 py-2.5">
                        <span className="font-mono tabular">
                          {formatDate(goal.effective_from)}
                        </span>
                        {index === 0 && (
                          <span className="ml-2 rounded border border-accent/30 bg-accent-soft px-1.5 py-0.5 text-[11px] text-accent">
                            Active
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-2.5 text-right font-mono tabular">
                        {goal.calorie_target === null ? "—" : formatNumber(goal.calorie_target)}
                      </td>
                      <td className="px-3 py-2.5 text-right font-mono tabular">
                        {formatAmount(goal.protein_g)}
                      </td>
                      <td className="px-3 py-2.5 text-right font-mono tabular">
                        {formatAmount(goal.carbs_g)}
                      </td>
                      <td className="px-3 py-2.5 text-right font-mono tabular">
                        {formatAmount(goal.fat_g)}
                      </td>
                      <td className="px-3 py-2.5 text-right font-mono tabular">
                        {formatAmount(goal.weight_target_kg)}
                      </td>
                      <td className="px-5 py-2.5 text-right">
                        <button
                          className="text-[13px] text-ink-muted underline hover:text-danger"
                          onClick={() => removeGoal.mutate(goal.id)}
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </>
  );
}

function WeightPanel() {
  const weights = useWeights();
  const record = useRecordWeight();
  const [weight, setWeight] = useState("");
  const [date, setDate] = useState(today());

  const latest = weights.data?.items[0];

  return (
    <Card>
      <CardHeader title="Weight" subtitle="One reading per day." />
      <div className="p-5">
        {latest ? (
          <p className="mb-4 text-[13px] text-ink-soft">
            Latest <Value className="text-[15px]">{formatAmount(latest.weight_kg)} kg</Value>{" "}
            <span className="text-ink-muted">on {formatDate(latest.logged_on)}</span>
          </p>
        ) : (
          <p className="mb-4 text-[13px] text-ink-muted">No readings recorded yet.</p>
        )}

        <form
          className="space-y-3"
          onSubmit={(event) => {
            event.preventDefault();
            record.mutate(
              { logged_on: date, weight_kg: Number(weight) },
              { onSuccess: () => setWeight("") },
            );
          }}
        >
          <Field label="Date">
            <Input type="date" max={today()} value={date} onChange={(e) => setDate(e.target.value)} />
          </Field>
          <Field label="Weight (kg)">
            <Input
              type="number"
              step="any"
              min="0"
              required
              value={weight}
              onChange={(e) => setWeight(e.target.value)}
            />
          </Field>
          <Button type="submit" variant="primary" className="w-full" disabled={record.isPending}>
            {record.isPending ? "Saving…" : "Record weight"}
          </Button>
        </form>
      </div>
    </Card>
  );
}
