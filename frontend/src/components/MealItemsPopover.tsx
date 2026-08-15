/**
 * What was actually eaten at a meal, revealed from its item count.
 *
 * The dashboard's by-meal table answers "how much" but not "what", and going to Entries to find
 * out is a lot of navigation for a question this small. The detail is already loaded, so opening
 * it costs nothing.
 *
 * **Deliberately not hover-only.** A tooltip that appears on `mouseenter` alone is invisible to
 * anyone using a keyboard and unreachable on a touchscreen, which would make the item list simply
 * not exist for those users. This opens on hover, on focus and on tap, closes on Escape or on
 * leaving, and the trigger is a real button so it lands in the tab order.
 */

import { useId, useRef, useState } from "react";

import { formatNumber } from "../lib/format";
import type { FoodEntry } from "../lib/types";
import { Value } from "./ui";

export function MealItemsPopover({
  label,
  items,
}: {
  /** Describes the trigger for screen readers, e.g. "3 items at breakfast". */
  label: string;
  items: FoodEntry[];
}) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const closeTimer = useRef<number | undefined>(undefined);

  if (items.length === 0) return <span className="text-ink-muted">—</span>;

  // A small grace period stops the panel flickering shut when the pointer crosses the gap
  // between the trigger and the panel.
  const scheduleClose = () => {
    window.clearTimeout(closeTimer.current);
    closeTimer.current = window.setTimeout(() => setOpen(false), 120);
  };
  const cancelClose = () => window.clearTimeout(closeTimer.current);

  return (
    <span className="relative inline-block" onMouseLeave={scheduleClose}>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={open ? panelId : undefined}
        aria-label={label}
        className="underline decoration-dotted underline-offset-4 hover:text-ink"
        onMouseEnter={() => {
          cancelClose();
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={scheduleClose}
        onClick={() => setOpen((current) => !current)}
        onKeyDown={(event) => event.key === "Escape" && setOpen(false)}
      >
        {items.length} {items.length === 1 ? "item" : "items"}
      </button>

      {open && (
        <div
          id={panelId}
          role="tooltip"
          onMouseEnter={cancelClose}
          onMouseLeave={scheduleClose}
          className="absolute right-0 z-20 mt-1 w-64 rounded-md border border-rule bg-surface p-3 text-left shadow-lg"
        >
          <table className="w-full text-[12px]">
            <tbody>
              {items.map((item) => (
                <tr key={item.id} className="border-b border-rule-soft last:border-0">
                  <td className="py-1 pr-3">
                    {item.food_name}
                    <span className="ml-1 text-ink-muted">
                      {formatNumber(item.quantity, item.quantity % 1 ? 1 : 0)} {item.unit}
                    </span>
                  </td>
                  <td className="py-1 text-right whitespace-nowrap">
                    <Value>{formatNumber(item.calories)}</Value>
                    <span className="ml-1 text-ink-muted">kcal</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </span>
  );
}
