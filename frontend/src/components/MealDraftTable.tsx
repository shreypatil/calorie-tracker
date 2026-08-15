/**
 * Rows a machine proposed, laid out for a person to check.
 *
 * Two features produce this exact object — the assistant's `log_meal` and a photo of a plate —
 * and both need the same thing: the foods, what each contributes, a total, and the ability to
 * fix a figure before it is saved. Keeping one table means a correction to how drafts read
 * lands in both places, and neither drifts into its own dialect.
 *
 * Built as a nutrition panel rather than a list, because that is what it is: a rule under the
 * column heads, a heavier rule above the total, mono tabular figures aligned on the decimal.
 */

import { formatNumber, MEAL_LABELS } from "../lib/format";
import type { MealType } from "../lib/types";
import { Input, Value } from "./ui";

/** The minimum a row needs to be reviewable. Both callers project onto this. */
export interface DraftRowView {
  food_name: string;
  meal_type: MealType;
  quantity: number;
  unit: string;
  calories: number;
}

export function MealDraftTable({
  rows,
  editable,
  onChange,
  issuesFor,
}: {
  rows: DraftRowView[];
  editable: boolean;
  onChange?: (index: number, patch: Partial<DraftRowView>) => void;
  /** Per-row warnings — a dropped value, an estimate, an arithmetic mismatch. */
  issuesFor?: (index: number) => string[];
}) {
  const total = rows.reduce((sum, row) => sum + (Number(row.calories) || 0), 0);

  return (
    <table className="w-full text-[13px]">
      <thead>
        <tr className="border-b border-rule">
          <th className="eyebrow pb-1.5 text-left font-normal">Food</th>
          <th className="eyebrow pb-1.5 text-left font-normal">Meal</th>
          <th className="eyebrow pb-1.5 text-right font-normal">Qty</th>
          <th className="eyebrow pb-1.5 text-right font-normal">Calories</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row, index) => {
          const issues = issuesFor?.(index) ?? [];
          return (
            <tr key={index} className="border-b border-rule-soft last:border-0 align-top">
              <td className="py-1.5 pr-3">
                {editable && onChange ? (
                  <Input
                    aria-label={`Food name for row ${index + 1}`}
                    value={row.food_name}
                    onChange={(event) => onChange(index, { food_name: event.target.value })}
                  />
                ) : (
                  row.food_name
                )}
                {issues.map((issue) => (
                  <p key={issue} className="mt-1 text-[12px] text-ink-muted">
                    {issue}
                  </p>
                ))}
              </td>
              <td className="py-1.5 pr-3 text-ink-muted">
                {MEAL_LABELS[row.meal_type] ?? row.meal_type}
              </td>
              <td className="py-1.5 pr-3 text-right whitespace-nowrap">
                <Value>{formatNumber(row.quantity, row.quantity % 1 ? 1 : 0)}</Value>
                <span className="ml-1 text-[12px] text-ink-muted">{row.unit}</span>
              </td>
              <td className="w-28 py-1.5 text-right">
                {editable && onChange ? (
                  <Input
                    aria-label={`Calories for row ${index + 1}`}
                    type="number"
                    min={0}
                    className="text-right"
                    value={row.calories}
                    onChange={(event) => onChange(index, { calories: Number(event.target.value) })}
                  />
                ) : (
                  <Value>{formatNumber(row.calories)}</Value>
                )}
              </td>
            </tr>
          );
        })}
      </tbody>
      <tfoot>
        <tr className="border-t-2 border-ink">
          <td className="eyebrow pt-2" colSpan={3}>
            Total
          </td>
          <td className="pt-2 text-right">
            <Value className="font-semibold">{formatNumber(total)}</Value>
            <span className="ml-1 text-[12px] text-ink-muted">kcal</span>
          </td>
        </tr>
      </tfoot>
    </table>
  );
}
