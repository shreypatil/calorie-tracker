/**
 * Micronutrient summary (FR-4).
 *
 * Eleven nutrients would need eleven hues nobody can tell apart, so this is a
 * table with a meter per row: the numbers stay exact and readable, and progress
 * against target is encoded by length rather than colour.
 */

import { Meter } from "../ui";
import { formatAmount, nutrientLabel, nutrientUnit } from "../../lib/format";
import type { MicronutrientRow } from "../../lib/types";

export function MicroTable({ rows, days }: { rows: MicronutrientRow[]; days: number }) {
  const anyLogged = rows.some((row) => row.total > 0);

  if (!anyLogged) {
    return (
      <p className="px-5 py-10 text-center text-[13px] text-ink-muted">
        No micronutrients recorded in this range. Add them when logging a meal to see them here.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto px-2 pb-2">
      <table className="w-full min-w-[36rem] border-collapse text-[13px]">
        <thead>
          <tr className="border-b border-rule">
            <th className="eyebrow px-3 py-2 text-left font-normal">Nutrient</th>
            <th className="eyebrow px-3 py-2 text-right font-normal">Total</th>
            <th className="eyebrow px-3 py-2 text-right font-normal">Daily avg</th>
            <th className="eyebrow px-3 py-2 text-right font-normal">Target</th>
            <th className="eyebrow w-40 px-3 py-2 text-left font-normal">Against target</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.name} className="border-b border-rule-soft last:border-0">
              <td className="px-3 py-2">{nutrientLabel(row.name)}</td>
              <td className="px-3 py-2 text-right font-mono tabular">
                {formatAmount(row.total)}
                <span className="ml-1 text-ink-muted">{nutrientUnit(row.name)}</span>
              </td>
              <td className="px-3 py-2 text-right font-mono tabular">
                {formatAmount(row.daily_average)}
              </td>
              <td className="px-3 py-2 text-right font-mono tabular text-ink-muted">
                {row.target === null ? "—" : formatAmount(row.target)}
              </td>
              <td className="px-3 py-2">
                <Meter value={row.daily_average} target={row.target} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="px-3 pt-3 text-[12px] text-ink-muted">
        Daily average across {days} {days === 1 ? "day" : "days"}. Targets come from the goal in
        force at the end of the range.
      </p>
    </div>
  );
}
