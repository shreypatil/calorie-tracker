/**
 * Build your own chart: pick nutrients, pick a range, see them overlaid.
 *
 * This is the payoff for the registry design on the server. The metric list is fetched from
 * `GET /reports/catalogue` rather than hard-coded, so it is always exactly what the backend will
 * accept — add a metric to the registry and it appears here with no frontend change at all.
 *
 * The cap of five simultaneous series is not arbitrary. `scripts/validate-palette.mjs` shows five
 * is the most that stay mutually distinguishable under protanopia, deuteranopia and tritanopia
 * while remaining in this app's colour register. Likewise the two-unit limit: a third unit family
 * has nowhere to go but onto an axis that misrepresents it.
 */

import { useState } from "react";

import { OverlayChart } from "./OverlayChart";
import { ChartFrame, Legend } from "./chartTheme";
import { MAX_OVERLAY_SERIES, OVERLAY_SERIES, unitFamilies } from "./theme";
import { Alert, ErrorNote, Loading, Select } from "../ui";
import { cx } from "../../lib/cx";
import { nutrientLabel, nutrientUnit } from "../../lib/format";
import { useAggregate, useReportCatalogue } from "../../lib/queries";
import type { Granularity } from "../../lib/types";

const GRANULARITIES: Granularity[] = ["day", "week", "month"];

/** `entry_count` is a tally, not a nutrient — it has no unit and no place on a nutrient axis. */
const EXCLUDED = new Set(["entry_count"]);

export function CustomChart({
  dateFrom,
  dateTo,
}: {
  dateFrom: string;
  dateTo: string;
}) {
  const catalogue = useReportCatalogue();
  const [selected, setSelected] = useState<string[]>(["calories", "protein_g"]);
  const [granularity, setGranularity] = useState<Granularity>("day");

  const result = useAggregate({
    metrics: selected,
    group_by: [granularity],
    date_from: dateFrom,
    date_to: dateTo,
    fill_gaps: true,
  });

  const available = (catalogue.data?.metrics ?? []).filter((metric) => !EXCLUDED.has(metric));

  function toggle(metric: string) {
    setSelected((current) => {
      if (current.includes(metric)) return current.filter((name) => name !== metric);
      if (current.length >= MAX_OVERLAY_SERIES) return current;
      if (unitFamilies([...current, metric]).length > 2) return current;
      return [...current, metric];
    });
  }

  /** Why a given metric cannot be added right now — said plainly rather than just disabled. */
  function blockedReason(metric: string): string | null {
    if (selected.includes(metric)) return null;
    if (selected.length >= MAX_OVERLAY_SERIES) return `Up to ${MAX_OVERLAY_SERIES} at once`;
    if (unitFamilies([...selected, metric]).length > 2) return "Would need a third axis";
    return null;
  }

  const families = unitFamilies(selected);
  const points = (result.data?.rows ?? []).map((row) => ({
    ...row,
    bucket: String(row[granularity]),
  }));

  return (
    <ChartFrame
      title="Build a chart"
      description="Pick any nutrients to plot together over the selected range."
      legend={
        selected.length > 0 ? (
          <Legend
            series={selected.map((metric, index) => ({
              key: metric,
              label: `${nutrientLabel(metric)} (${nutrientUnit(metric)})`,
              color: OVERLAY_SERIES[index % OVERLAY_SERIES.length],
            }))}
          />
        ) : undefined
      }
      controls={
        <div className="w-36">
          <Select
            aria-label="Time bucket"
            value={granularity}
            onChange={(event) => setGranularity(event.target.value as Granularity)}
          >
            {GRANULARITIES.map((option) => (
              <option key={option} value={option}>
                By {option}
              </option>
            ))}
          </Select>
        </div>
      }
    >
      <div className="mb-4 flex flex-wrap gap-1.5">
        {catalogue.isLoading && <Loading label="Loading nutrients" />}
        {available.map((metric) => {
          const active = selected.includes(metric);
          const blocked = blockedReason(metric);
          return (
            <button
              key={metric}
              type="button"
              aria-pressed={active}
              disabled={Boolean(blocked)}
              title={blocked ?? undefined}
              onClick={() => toggle(metric)}
              className={cx(
                "rounded-full border px-2.5 py-1 text-[12px]",
                active
                  ? "border-accent bg-accent-soft text-ink"
                  : "border-rule text-ink-soft hover:bg-paper",
                blocked && "cursor-not-allowed opacity-40",
              )}
            >
              {nutrientLabel(metric)}
            </button>
          );
        })}
      </div>

      {selected.length === 0 ? (
        <Alert tone="info">Pick at least one nutrient to plot.</Alert>
      ) : result.isLoading ? (
        <Loading />
      ) : result.error ? (
        <ErrorNote error={result.error} />
      ) : (
        <>
          <OverlayChart points={points} metrics={selected} />
          {families.length > 1 && (
            <p className="mt-2 text-[12px] text-ink-muted">
              Two scales in use: {families[0]} on the left axis, {families[1]} on the right.
            </p>
          )}
        </>
      )}
    </ChartFrame>
  );
}
