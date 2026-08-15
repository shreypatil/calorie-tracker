/**
 * Every parsed row, with its status and why.
 *
 * Rows that could not be read are shown rather than hidden — a diary that
 * imports 58 of 62 rows should say which four were dropped and what went
 * wrong, not quietly lose them.
 */

import { cx } from "../../lib/cx";
import { MEAL_LABELS, formatAmount, formatDate, formatNumber } from "../../lib/format";
import type { DraftRow, RowStatus } from "../../lib/types";

const STATUS_STYLES: Record<RowStatus, string> = {
  ok: "border-good/30 bg-accent-soft text-good",
  needs_review: "border-warn/30 bg-[#faf3e2] text-warn",
  invalid: "border-danger/30 bg-danger-soft text-danger",
};

const STATUS_LABELS: Record<RowStatus, string> = {
  ok: "Ready",
  needs_review: "Check",
  invalid: "Unreadable",
};

function StatusChip({ status }: { status: RowStatus }) {
  return (
    <span
      className={cx(
        "inline-block whitespace-nowrap rounded border px-1.5 py-0.5 text-[11px]",
        STATUS_STYLES[status],
      )}
    >
      {STATUS_LABELS[status]}
    </span>
  );
}

export function ReviewTable({
  rows,
  selected,
  onToggle,
  onToggleAll,
}: {
  rows: DraftRow[];
  selected: Set<number>;
  onToggle: (index: number) => void;
  onToggleAll: (checked: boolean) => void;
}) {
  const selectable = rows.filter((row) => row.entry !== null);
  const allSelected = selectable.length > 0 && selectable.every((row) => selected.has(row.index));

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[52rem] border-collapse text-[13px]">
        <thead>
          <tr className="border-b border-rule">
            <th className="w-10 px-5 py-2">
              <input
                type="checkbox"
                aria-label="Select every importable row"
                checked={allSelected}
                onChange={(event) => onToggleAll(event.target.checked)}
              />
            </th>
            <th className="eyebrow px-2 py-2 text-left font-normal">Status</th>
            <th className="eyebrow px-3 py-2 text-left font-normal">Date</th>
            <th className="eyebrow px-3 py-2 text-left font-normal">Meal</th>
            <th className="eyebrow px-3 py-2 text-left font-normal">Food</th>
            <th className="eyebrow px-3 py-2 text-right font-normal">Calories</th>
            <th className="eyebrow px-3 py-2 text-right font-normal">P / C / F</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const entry = row.entry;
            const importable = entry !== null;

            return (
              <tr
                key={row.index}
                className={cx(
                  "border-b border-rule-soft last:border-0 align-top",
                  !importable && "bg-paper",
                )}
              >
                <td className="px-5 py-2.5">
                  <input
                    type="checkbox"
                    aria-label={`Include row ${row.index + 1}`}
                    disabled={!importable}
                    checked={selected.has(row.index)}
                    onChange={() => onToggle(row.index)}
                  />
                </td>
                <td className="px-2 py-2.5">
                  <StatusChip status={row.status} />
                </td>

                {importable ? (
                  <>
                    <td className="whitespace-nowrap px-3 py-2.5 font-mono tabular text-ink-muted">
                      {formatDate(entry.consumed_on)}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5">
                      {MEAL_LABELS[entry.meal_type]}
                    </td>
                    <td className="px-3 py-2.5">
                      {entry.food_name}
                      <span className="ml-1.5 text-ink-muted">
                        {formatAmount(entry.quantity)} {entry.unit}
                      </span>
                      <Issues row={row} />
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5 text-right font-mono tabular">
                      {formatNumber(entry.calories)}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5 text-right font-mono tabular text-ink-muted">
                      {formatAmount(entry.protein_g)} / {formatAmount(entry.carbs_g)} /{" "}
                      {formatAmount(entry.fat_g)}
                    </td>
                  </>
                ) : (
                  <td className="px-3 py-2.5 text-ink-muted" colSpan={5}>
                    {/* Nothing usable was parsed, so show the source cells
                        instead — that is what the user needs to judge it. */}
                    <span className="font-mono text-[12px]">
                      {Object.values(row.raw).filter(Boolean).join("  ·  ") || "empty row"}
                    </span>
                    <Issues row={row} />
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function Issues({ row }: { row: DraftRow }) {
  if (row.issues.length === 0) return null;
  return (
    <ul className="mt-1 space-y-0.5">
      {row.issues.map((issue, index) => (
        <li key={index} className="text-[12px] text-ink-muted">
          {issue.message}
        </li>
      ))}
    </ul>
  );
}
