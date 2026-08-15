/** The four required visualizations (FR-4), over one shared range. */

import { useState } from "react";
import { PageHeading } from "../components/Layout";
import { Card, ErrorNote, Loading, Select, Value } from "../components/ui";
import { ChartFrame, Legend } from "../components/charts/chartTheme";
import { TrendChart } from "../components/charts/TrendChart";
import { MacroChart } from "../components/charts/MacroChart";
import { GoalVsActualChart } from "../components/charts/GoalVsActualChart";
import { MicroTable } from "../components/charts/MicroTable";
import { useGoalVsActual, useMacros, useMicros, useTrend } from "../lib/queries";
import { daysAgo, formatAmount, formatDate, today } from "../lib/format";
import { MACROS, type Granularity } from "../lib/types";

const RANGES = [
  { label: "Last 14 days", days: 13, granularity: "day" as const },
  { label: "Last 28 days", days: 27, granularity: "day" as const },
  { label: "Last 12 weeks", days: 83, granularity: "week" as const },
];

export function Reports() {
  const [rangeIndex, setRangeIndex] = useState(1);
  const preset = RANGES[rangeIndex];

  const range = {
    date_from: daysAgo(preset.days),
    date_to: today(),
    granularity: preset.granularity as Granularity,
  };

  const trend = useTrend(range);
  const macros = useMacros(range);
  const micros = useMicros({ date_from: range.date_from, date_to: range.date_to });
  const comparison = useGoalVsActual(range);

  const rangeControl = (
    <Select
      className="w-auto"
      aria-label="Reporting period"
      value={rangeIndex}
      onChange={(event) => setRangeIndex(Number(event.target.value))}
    >
      {RANGES.map((option, index) => (
        <option key={option.label} value={index}>
          {option.label}
        </option>
      ))}
    </Select>
  );

  const bucketNote = `Grouped by ${preset.granularity}.`;

  return (
    <>
      <PageHeading
        title="Reports"
        description={`${formatDate(range.date_from)} – ${formatDate(range.date_to)}`}
        actions={rangeControl}
      />

      <div className="space-y-5">
        <ChartFrame title="Calorie intake" description={`Energy logged over time. ${bucketNote}`}>
          {trend.isLoading ? (
            <Loading />
          ) : trend.error ? (
            <ErrorNote error={trend.error} />
          ) : (
            <TrendChart points={trend.data?.points ?? []} />
          )}
        </ChartFrame>

        <ChartFrame
          title="Macronutrients"
          description={`Grams of protein, carbs and fat. ${bucketNote}`}
          legend={<Legend series={MACROS.map((key) => ({ key }))} />}
          footer={
            macros.data ? (
              <p className="text-[12px] text-ink-muted">
                Share of calories:{" "}
                {MACROS.map((macro, index) => (
                  <span key={macro}>
                    {index > 0 && " · "}
                    {macro === "protein_g" ? "protein" : macro === "carbs_g" ? "carbs" : "fat"}{" "}
                    <Value>{macros.data.share_of_calories[macro]}%</Value>
                  </span>
                ))}
              </p>
            ) : null
          }
        >
          {macros.isLoading ? (
            <Loading />
          ) : macros.error ? (
            <ErrorNote error={macros.error} />
          ) : (
            <MacroChart points={macros.data?.points ?? []} />
          )}
        </ChartFrame>

        <ChartFrame
          title="Goal vs actual"
          description={`Calories logged against the goal in force at the time. ${bucketNote}`}
          legend={
            <Legend
              series={[
                { key: "calories", label: "Logged" },
                { key: "target", label: "Target" },
              ]}
            />
          }
        >
          {comparison.isLoading ? (
            <Loading />
          ) : comparison.error ? (
            <ErrorNote error={comparison.error} />
          ) : (
            <GoalVsActualChart points={comparison.data?.points ?? []} />
          )}
        </ChartFrame>

        <Card>
          <div className="border-b border-rule px-5 py-4">
            <h2 className="text-[15px] font-semibold tracking-tight">Micronutrients</h2>
            <p className="mt-0.5 text-[13px] text-ink-muted">
              Totals and daily averages across the period.
            </p>
          </div>
          {micros.isLoading ? (
            <Loading />
          ) : micros.error ? (
            <ErrorNote error={micros.error} />
          ) : (
            <MicroTable rows={micros.data?.nutrients ?? []} days={micros.data?.days ?? 0} />
          )}
        </Card>

        {macros.data && (
          <p className="text-[12px] text-ink-muted">
            Totals for the period: protein{" "}
            <Value>{formatAmount(macros.data.totals.protein_g)} g</Value>, carbs{" "}
            <Value>{formatAmount(macros.data.totals.carbs_g)} g</Value>, fat{" "}
            <Value>{formatAmount(macros.data.totals.fat_g)} g</Value>.
          </p>
        )}
      </div>
    </>
  );
}
