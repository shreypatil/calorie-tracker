/** Today at a glance: the one question the app exists to answer. */

import { Link } from "react-router-dom";
import { PageHeading } from "../components/Layout";
import { Card, CardHeader, ErrorNote, Loading, Meter, Value } from "../components/ui";
import { TrendChart } from "../components/charts/TrendChart";
import { ChartFrame } from "../components/charts/chartTheme";
import { useDailySummary, useTrend } from "../lib/queries";
import {
  MEAL_LABELS,
  daysAgo,
  formatAmount,
  formatDayLabel,
  formatNumber,
  today,
} from "../lib/format";
import { MACROS, type DailySummary } from "../lib/types";

export function Dashboard() {
  const day = today();
  const summary = useDailySummary(day);
  const trend = useTrend({ date_from: daysAgo(13), date_to: day, granularity: "day" });

  if (summary.isLoading) return <Loading />;
  if (summary.error) return <ErrorNote error={summary.error} />;
  if (!summary.data) return null;

  const data = summary.data;

  return (
    <>
      <PageHeading
        title={formatDayLabel(day)}
        description="Everything logged today, measured against your goal."
      />

      <div className="grid gap-5 lg:grid-cols-3">
        <CaloriePanel data={data} />
        <MacroPanel data={data} />
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <ChartFrame title="Last 14 days" description="Calories logged each day.">
            {trend.isLoading ? (
              <Loading />
            ) : trend.error ? (
              <ErrorNote error={trend.error} />
            ) : (
              <TrendChart
                points={trend.data?.points ?? []}
                target={data.goal?.calorie_target ?? null}
                targetLabel={`Goal ${formatNumber(data.goal?.calorie_target ?? 0)}`}
              />
            )}
          </ChartFrame>
        </div>

        <MealsPanel data={data} />
      </div>
    </>
  );
}

function CaloriePanel({ data }: { data: DailySummary }) {
  const target = data.goal?.calorie_target ?? null;
  const consumed = data.totals.calories ?? 0;
  const remaining = data.remaining_calories;
  const over = remaining !== null && remaining < 0;

  return (
    <Card className="p-5 lg:col-span-2">
      <p className="eyebrow">Calories</p>

      <div className="mt-2 flex flex-wrap items-baseline gap-x-3">
        <Value className="text-[44px] leading-none font-medium">{formatNumber(consumed)}</Value>
        <span className="text-[14px] text-ink-muted">
          {target ? `of ${formatNumber(target)} kcal` : "kcal logged"}
        </span>
      </div>

      <div className="mt-4">
        <Meter value={consumed} target={target} />
      </div>

      <p className="mt-3 text-[13px]">
        {target === null ? (
          <span className="text-ink-muted">
            No goal set.{" "}
            <Link className="text-accent underline" to="/goals">
              Set one
            </Link>{" "}
            to track against a target.
          </span>
        ) : over ? (
          <span className="text-warn">
            <Value>{formatNumber(Math.abs(remaining!))}</Value> kcal over your goal.
          </span>
        ) : (
          <span className="text-ink-soft">
            <Value>{formatNumber(remaining!)}</Value> kcal remaining.
          </span>
        )}
      </p>
    </Card>
  );
}

function MacroPanel({ data }: { data: DailySummary }) {
  const goal = data.goal;

  return (
    <Card className="p-5">
      <p className="eyebrow">Macros</p>
      <dl className="mt-3 space-y-3">
        {MACROS.map((macro) => {
          const value = data.totals[macro] ?? 0;
          const target = goal?.[macro] ?? null;
          return (
            <div key={macro}>
              <div className="flex items-baseline justify-between text-[13px]">
                <dt className="flex items-center gap-1.5">
                  <span
                    aria-hidden
                    className="inline-block size-2.5 rounded-[2px]"
                    style={{ backgroundColor: `var(--color-${macro.replace("_g", "")})` }}
                  />
                  {macro === "protein_g" ? "Protein" : macro === "carbs_g" ? "Carbs" : "Fat"}
                </dt>
                <dd className="font-mono tabular">
                  {formatAmount(value)}
                  <span className="text-ink-muted">
                    {target ? ` / ${formatAmount(target)} g` : " g"}
                  </span>
                </dd>
              </div>
              <div className="mt-1.5">
                <Meter
                  value={value}
                  target={target}
                  tone={macro.replace("_g", "") as "protein" | "carbs" | "fat"}
                />
              </div>
            </div>
          );
        })}
      </dl>
    </Card>
  );
}

function MealsPanel({ data }: { data: DailySummary }) {
  const logged = data.by_meal.some((meal) => meal.entry_count > 0);

  return (
    <Card>
      <CardHeader title="By meal" subtitle={logged ? undefined : "Nothing logged yet today."} />
      <table className="w-full border-collapse text-[13px]">
        <tbody>
          {data.by_meal.map((meal) => (
            <tr key={meal.meal_type} className="border-b border-rule-soft last:border-0">
              <td className="px-5 py-2.5">{MEAL_LABELS[meal.meal_type]}</td>
              <td className="px-5 py-2.5 text-right text-ink-muted">
                {meal.entry_count === 0
                  ? "—"
                  : `${meal.entry_count} ${meal.entry_count === 1 ? "item" : "items"}`}
              </td>
              <td className="px-5 py-2.5 text-right font-mono tabular">
                {formatNumber(meal.calories)}
                <span className="ml-1 text-ink-muted">kcal</span>
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          {/* The heavier rule above a total is the nutrition-panel convention. */}
          <tr className="border-t-2 border-ink">
            <td className="px-5 py-2.5 font-medium">Total</td>
            <td />
            <td className="px-5 py-2.5 text-right font-mono tabular font-medium">
              {formatNumber(data.totals.calories ?? 0)}
              <span className="ml-1 font-normal text-ink-muted">kcal</span>
            </td>
          </tr>
        </tfoot>
      </table>
      <div className="border-t border-rule px-5 py-3">
        <Link to="/entries" className="text-[13px] text-accent underline">
          Log a meal
        </Link>
      </div>
    </Card>
  );
}
