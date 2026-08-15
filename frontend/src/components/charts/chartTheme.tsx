/** Chart chrome shared by every chart: tooltip, legend, and the card frame. */

import type { ReactNode } from "react";
import { formatNumber, nutrientLabel, nutrientUnit } from "../../lib/format";
import { SERIES } from "./theme";

/** One tooltip style for every chart. Values keep the mono treatment. */
export function ChartTooltip({
  active,
  payload,
  label,
  labelFormatter,
  unit,
}: {
  active?: boolean;
  payload?: { name: string; value: number; color: string; dataKey: string }[];
  label?: string;
  labelFormatter?: (value: string) => string;
  unit?: string;
}) {
  if (!active || !payload?.length) return null;

  return (
    <div className="rounded border border-rule bg-surface px-3 py-2 text-[12px] shadow-sm">
      <p className="mb-1.5 font-medium">
        {labelFormatter && label ? labelFormatter(label) : label}
      </p>
      <table className="w-full border-collapse">
        <tbody>
          {payload.map((item) => (
            <tr key={item.dataKey}>
              <td className="pr-3">
                <span className="inline-flex items-center gap-1.5">
                  <span
                    aria-hidden
                    className="inline-block size-2 rounded-[2px]"
                    style={{ backgroundColor: item.color }}
                  />
                  <span className="text-ink-soft">{item.name}</span>
                </span>
              </td>
              <td className="text-right font-mono tabular">
                {formatNumber(item.value)}
                <span className="ml-1 text-ink-muted">
                  {unit ?? nutrientUnit(item.dataKey)}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/**
 * Legend as real text with a colour chip — identity never rests on colour alone.
 *
 * `color` overrides the per-nutrient token, which the overlay chart needs: there the colour
 * comes from the series' slot rather than from which nutrient it happens to be.
 */
export function Legend({
  series,
}: {
  series: { key: string; label?: string; color?: string }[];
}) {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1">
      {series.map(({ key, label, color }) => (
        <li key={key} className="flex items-center gap-1.5 text-[12px] text-ink-soft">
          <span
            aria-hidden
            className="inline-block size-2.5 rounded-[2px]"
            style={{ backgroundColor: color ?? SERIES[key as keyof typeof SERIES] }}
          />
          {label ?? nutrientLabel(key)}
        </li>
      ))}
    </ul>
  );
}

export function ChartFrame({
  title,
  description,
  legend,
  controls,
  children,
  footer,
}: {
  title: string;
  description?: string;
  legend?: ReactNode;
  controls?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <section className="rounded-md border border-rule bg-surface">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-rule px-5 py-4">
        <div>
          <h2 className="text-[15px] font-semibold tracking-tight">{title}</h2>
          {description && <p className="mt-0.5 text-[13px] text-ink-muted">{description}</p>}
        </div>
        {controls}
      </div>

      <div className="px-2 pt-4">{children}</div>

      {(legend || footer) && (
        <div className="flex flex-wrap items-center justify-between gap-3 px-5 pb-4 pt-2">
          {legend}
          {footer}
        </div>
      )}
    </section>
  );
}
