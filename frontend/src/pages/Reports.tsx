/** The four required visualizations (FR-4), over one shared range. */

import { useState } from "react";
import { PageHeading } from "../components/Layout";
import { Button, Card, ErrorNote, Field, Input, Loading, Select, Value } from "../components/ui";
import { ChartFrame, Legend } from "../components/charts/chartTheme";
import { CustomChart } from "../components/charts/CustomChart";
import { MacroChart } from "../components/charts/MacroChart";
import { GoalVsActualChart } from "../components/charts/GoalVsActualChart";
import { MicroTable } from "../components/charts/MicroTable";
import { useCurrentGoal, useGoalVsActual, useMacros, useMicros } from "../lib/queries";
import { daysAgo, formatAmount, formatDate, nutrientLabel, today } from "../lib/format";
import { MACROS, MICRONUTRIENTS, type Granularity } from "../lib/types";

/** Shortcuts, not the only way in — the dates themselves are directly editable. */
const PRESETS = [
  { label: "14 days", days: 13, granularity: "day" as const },
  { label: "28 days", days: 27, granularity: "day" as const },
  { label: "12 weeks", days: 83, granularity: "week" as const },
  { label: "12 months", days: 364, granularity: "month" as const },
];

export function Reports() {
  const [range, setRange] = useState({
    date_from: daysAgo(27),
    date_to: today(),
    granularity: "day" as Granularity,
  });

  const [goalMetric, setGoalMetric] = useState("calories");

  const macros = useMacros(range);
  const micros = useMicros({ date_from: range.date_from, date_to: range.date_to });
  const comparison = useGoalVsActual(range);
  const goal = useCurrentGoal();

  const bucketNote = `Grouped by ${range.granularity}.`;

  /**
   * Only nutrients the user has actually set a target for.
   *
   * Offering all fifteen would mostly produce charts with bars and no target line, which reads as
   * a broken chart rather than as "you have not set that goal". Calories stay listed regardless so
   * the control is never empty.
   */
  const targetedMetrics = [
    "calories",
    ...MACROS.filter((macro) => goal.data?.[macro] != null),
    ...MICRONUTRIENTS.filter((micro) => goal.data?.micro_targets?.[micro] != null),
  ];

  return (
    <>
      <PageHeading
        title="Reports"
        description={`${formatDate(range.date_from)} – ${formatDate(range.date_to)}`}
      />

      <Card className="mb-5 p-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="From">
            <Input
              type="date"
              max={range.date_to}
              value={range.date_from}
              onChange={(event) =>
                setRange((current) => ({ ...current, date_from: event.target.value }))
              }
            />
          </Field>
          <Field label="To">
            <Input
              type="date"
              min={range.date_from}
              max={today()}
              value={range.date_to}
              onChange={(event) =>
                setRange((current) => ({ ...current, date_to: event.target.value }))
              }
            />
          </Field>
          <Field label="Group by">
            <Select
              value={range.granularity}
              onChange={(event) =>
                setRange((current) => ({
                  ...current,
                  granularity: event.target.value as Granularity,
                }))
              }
            >
              {(["day", "week", "month"] as Granularity[]).map((option) => (
                <option key={option} value={option}>
                  {option[0].toUpperCase() + option.slice(1)}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Quick ranges">
            <div className="flex flex-wrap gap-1.5">
              {PRESETS.map((preset) => (
                <Button
                  key={preset.label}
                  type="button"
                  onClick={() =>
                    setRange({
                      date_from: daysAgo(preset.days),
                      date_to: today(),
                      granularity: preset.granularity,
                    })
                  }
                >
                  {preset.label}
                </Button>
              ))}
            </div>
          </Field>
        </div>
      </Card>

      <div className="space-y-5">
        <CustomChart dateFrom={range.date_from} dateTo={range.date_to} />
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
          description={`${nutrientLabel(goalMetric)} logged against the goal in force at the time. ${bucketNote}`}
          controls={
            <div className="w-44">
              <Select
                aria-label="Nutrient to compare"
                value={goalMetric}
                onChange={(event) => setGoalMetric(event.target.value)}
              >
                {targetedMetrics.map((metric) => (
                  <option key={metric} value={metric}>
                    {nutrientLabel(metric)}
                  </option>
                ))}
              </Select>
            </div>
          }
          legend={
            <Legend
              series={[
                { key: goalMetric, label: `${nutrientLabel(goalMetric)} logged` },
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
            <GoalVsActualChart points={comparison.data?.points ?? []} metric={goalMetric} />
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
