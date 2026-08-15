/**
 * A change the assistant wants to make, shown before it happens.
 *
 * This is the visible half of the confirmation gate: the assistant can propose, but only
 * this card can commit. It is deliberately built like the nutrition panel the rest of the
 * app uses — rules, mono tabular figures, uppercase micro-labels — rather than like a chat
 * bubble, because what it shows is a record about to be written, not a remark.
 *
 * Meal drafts are editable in place. The assistant estimates nutrition figures (there is no
 * food database), so the numbers are a starting point, and correcting one before committing
 * is the normal case rather than an edge case.
 */

import { useState } from "react";

import { formatNumber, MEAL_LABELS } from "../../lib/format";
import type { DraftMealItem, PendingAction } from "../../lib/types";
import { Button, Input, Value } from "../ui";
import { cx } from "../../lib/cx";

function isMealDraft(action: PendingAction): boolean {
  return action.tool === "log_meal" && Array.isArray(action.arguments.items);
}

function draftItems(action: PendingAction): DraftMealItem[] {
  return (action.arguments.items as DraftMealItem[]) ?? [];
}

/** Argument keys that carry no meaning for a reader. */
const HIDDEN_KEYS = new Set(["entry_id"]);

function readableKey(key: string): string {
  return key.replace(/_/g, " ").replace(/\bg\b/, "(g)").replace(/\bkg\b/, "(kg)");
}

function MealTable({
  items,
  editable,
  onChange,
}: {
  items: DraftMealItem[];
  editable: boolean;
  onChange: (index: number, patch: Partial<DraftMealItem>) => void;
}) {
  const total = items.reduce((sum, item) => sum + (Number(item.calories) || 0), 0);

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
        {items.map((item, index) => (
          <tr key={index} className="border-b border-rule-soft last:border-0">
            <td className="py-1.5 pr-3">
              {editable ? (
                <Input
                  aria-label={`Food name for row ${index + 1}`}
                  value={item.food_name}
                  onChange={(event) => onChange(index, { food_name: event.target.value })}
                />
              ) : (
                item.food_name
              )}
            </td>
            <td className="py-1.5 pr-3 text-ink-muted">
              {MEAL_LABELS[item.meal_type] ?? item.meal_type}
            </td>
            <td className="py-1.5 pr-3 text-right">
              <Value>
                {formatNumber(item.quantity, item.quantity % 1 ? 1 : 0)}
              </Value>
              <span className="ml-1 text-[12px] text-ink-muted">{item.unit}</span>
            </td>
            <td className="w-28 py-1.5 text-right">
              {editable ? (
                <Input
                  aria-label={`Calories for row ${index + 1}`}
                  type="number"
                  min={0}
                  className="text-right"
                  value={item.calories}
                  onChange={(event) =>
                    onChange(index, { calories: Number(event.target.value) })
                  }
                />
              ) : (
                <Value>{formatNumber(item.calories)}</Value>
              )}
            </td>
          </tr>
        ))}
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

function ArgumentList({ action }: { action: PendingAction }) {
  const rows = Object.entries(action.arguments).filter(
    ([key, value]) => !HIDDEN_KEYS.has(key) && value !== null && value !== undefined,
  );
  if (rows.length === 0) return null;

  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-1 text-[13px]">
      {rows.map(([key, value]) => (
        <div key={key} className="contents">
          <dt className="eyebrow self-center">{readableKey(key)}</dt>
          <dd className="text-right">
            {typeof value === "number" ? (
              <Value>{formatNumber(value, value % 1 ? 1 : 0)}</Value>
            ) : (
              String(value)
            )}
          </dd>
        </div>
      ))}
    </dl>
  );
}

const STATUS_LABEL: Record<PendingAction["status"], string> = {
  pending: "Draft · nothing saved yet",
  confirmed: "Saved",
  discarded: "Discarded",
};

export function DraftCard({
  action,
  onConfirm,
  onDiscard,
  busy = false,
  error,
}: {
  action: PendingAction;
  onConfirm: (args?: Record<string, unknown>) => void;
  onDiscard: () => void;
  busy?: boolean;
  error?: string;
}) {
  const [items, setItems] = useState<DraftMealItem[]>(() => draftItems(action));
  const pending = action.status === "pending";
  const meal = isMealDraft(action);

  const update = (index: number, patch: Partial<DraftMealItem>) =>
    setItems((current) =>
      current.map((item, position) => (position === index ? { ...item, ...patch } : item)),
    );

  return (
    <div
      className={cx(
        "mt-3 rounded-md border bg-surface px-4 py-3",
        pending ? "border-ink/25" : "border-rule",
      )}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2 pb-2">
        <span
          className={cx(
            "eyebrow",
            action.status === "confirmed" && "text-accent",
            action.status === "discarded" && "text-ink-muted",
          )}
        >
          {STATUS_LABEL[action.status]}
        </span>
        <span className="text-[13px] text-ink-soft">{action.summary}</span>
      </div>

      {meal ? (
        <MealTable items={items} editable={pending} onChange={update} />
      ) : (
        <ArgumentList action={action} />
      )}

      {error && <p className="mt-2 text-[12px] text-danger">{error}</p>}

      {pending && (
        <div className="mt-3 flex items-center gap-2 border-t border-rule pt-3">
          <Button
            variant="primary"
            disabled={busy}
            onClick={() => onConfirm(meal ? { items } : undefined)}
          >
            Confirm
          </Button>
          <Button disabled={busy} onClick={onDiscard}>
            Discard
          </Button>
          <span className="text-[12px] text-ink-muted">
            {meal ? "Estimates — edit anything that looks wrong." : "Nothing is saved yet."}
          </span>
        </div>
      )}
    </div>
  );
}
