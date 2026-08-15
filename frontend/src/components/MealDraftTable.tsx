/**
 * Rows a machine proposed, laid out for a person to check and correct.
 *
 * Two features produce this exact object — the assistant's `log_meal` and a photo of a plate — and
 * both need the same thing: the foods, what each contributes, a total, and the ability to fix any
 * figure before it is saved. Keeping one table means a correction to how drafts read lands in both
 * places, and neither drifts into its own dialect.
 *
 * Calories, protein, carbs and fat are editable inline because those are what people check. The
 * micronutrients are real values the extraction already produced, but eleven more inline columns
 * would make the table unreadable, so each row expands to reveal its own — the same fields the
 * single-item form offers, without paying for them on every row.
 */

import { Fragment, useState } from "react";

import { formatNumber, MEAL_LABELS, nutrientLabel, nutrientUnit } from "../lib/format";
import { DRAFT_MACROS, MICRONUTRIENTS, type MealType, type Micronutrient } from "../lib/types";
import { Input, Value } from "./ui";

const MACRO_HEADINGS: Record<(typeof DRAFT_MACROS)[number], string> = {
  calories: "Kcal",
  protein_g: "Protein",
  carbs_g: "Carbs",
  fat_g: "Fat",
};

/** What a row needs to be reviewable. Both callers project onto this. */
export interface DraftRowView {
  food_name: string;
  meal_type: MealType;
  quantity: number;
  unit: string;
  calories: number;
  protein_g?: number;
  carbs_g?: number;
  fat_g?: number;
  /** Micronutrients ride along so an expanded row can edit them. */
  [field: string]: unknown;
}

function NumberCell({
  label,
  value,
  editable,
  onChange,
}: {
  label: string;
  value: number | undefined;
  editable: boolean;
  onChange: (next: number) => void;
}) {
  if (!editable) return <Value>{formatNumber(value ?? 0)}</Value>;
  return (
    <Input
      aria-label={label}
      type="number"
      min={0}
      step="any"
      className="text-right"
      value={value ?? 0}
      onChange={(event) => onChange(Number(event.target.value))}
    />
  );
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
  const [expanded, setExpanded] = useState<number | null>(null);
  const canEdit = editable && Boolean(onChange);
  const totals = DRAFT_MACROS.map((macro) =>
    rows.reduce((sum, row) => sum + (Number(row[macro]) || 0), 0),
  );

  const set = (index: number, patch: Partial<DraftRowView>) => onChange?.(index, patch);

  return (
    <table className="w-full text-[13px]">
      <thead>
        <tr className="border-b border-rule">
          <th className="eyebrow pb-1.5 text-left font-normal">Food</th>
          <th className="eyebrow pb-1.5 text-left font-normal">Meal</th>
          <th className="eyebrow pb-1.5 text-right font-normal">Qty</th>
          {DRAFT_MACROS.map((macro) => (
            <th key={macro} className="eyebrow pb-1.5 pl-2 text-right font-normal">
              {MACRO_HEADINGS[macro]}
            </th>
          ))}
          {canEdit && <th className="w-8" />}
        </tr>
      </thead>

      <tbody>
        {rows.map((row, index) => {
          const issues = issuesFor?.(index) ?? [];
          const open = expanded === index;

          return (
            <Fragment key={index}>
              <tr className="border-b border-rule-soft align-top last:border-0">
                <td className="min-w-40 py-1.5 pr-3">
                  {canEdit ? (
                    <Input
                      aria-label={`Food name for row ${index + 1}`}
                      value={row.food_name}
                      onChange={(event) => set(index, { food_name: event.target.value })}
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

                <td className="py-1.5 pr-3 whitespace-nowrap text-ink-muted">
                  {MEAL_LABELS[row.meal_type] ?? row.meal_type}
                </td>

                <td className="py-1.5 pr-3 text-right whitespace-nowrap">
                  <Value>{formatNumber(row.quantity, row.quantity % 1 ? 1 : 0)}</Value>
                  <span className="ml-1 text-[12px] text-ink-muted">{row.unit}</span>
                </td>

                {DRAFT_MACROS.map((macro) => (
                  <td key={macro} className="w-24 py-1.5 pl-2 text-right">
                    <NumberCell
                      label={`${MACRO_HEADINGS[macro]} for row ${index + 1}`}
                      value={row[macro] as number | undefined}
                      editable={canEdit}
                      onChange={(next) => set(index, { [macro]: next })}
                    />
                  </td>
                ))}

                {canEdit && (
                  <td className="py-1.5 pl-2 text-right">
                    <button
                      type="button"
                      aria-expanded={open}
                      aria-label={`${open ? "Hide" : "Show"} micronutrients for ${row.food_name}`}
                      className="px-1 font-mono text-[15px] leading-none text-accent"
                      onClick={() => setExpanded(open ? null : index)}
                    >
                      {open ? "−" : "+"}
                    </button>
                  </td>
                )}
              </tr>

              {open && (
                <tr className="border-b border-rule-soft">
                  <td colSpan={4 + DRAFT_MACROS.length} className="px-1 pb-3">
                    <p className="eyebrow pt-1 pb-2">Micronutrients · {row.food_name}</p>
                    <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-4">
                      {MICRONUTRIENTS.map((name: Micronutrient) => (
                        <label key={name} className="block">
                          <span className="eyebrow block pb-1">
                            {nutrientLabel(name)} ({nutrientUnit(name)})
                          </span>
                          <Input
                            type="number"
                            min={0}
                            step="any"
                            placeholder="—"
                            className="text-right"
                            value={(row[name] as number | undefined) ?? ""}
                            onChange={(event) =>
                              set(index, {
                                [name]:
                                  event.target.value === ""
                                    ? undefined
                                    : Number(event.target.value),
                              })
                            }
                          />
                        </label>
                      ))}
                    </div>
                  </td>
                </tr>
              )}
            </Fragment>
          );
        })}
      </tbody>

      <tfoot>
        <tr className="border-t-2 border-ink">
          <td className="eyebrow pt-2" colSpan={3}>
            Total
          </td>
          {totals.map((total, position) => (
            <td key={DRAFT_MACROS[position]} className="pt-2 pl-2 text-right">
              <Value className={position === 0 ? "font-semibold" : undefined}>
                {formatNumber(total, total % 1 ? 1 : 0)}
              </Value>
            </td>
          ))}
          {canEdit && <td />}
        </tr>
      </tfoot>
    </table>
  );
}
