/**
 * A nutrient logged against the target that was in force (FR-4).
 *
 * Both series are the same nutrient, so they share one axis — a second scale would let the two be
 * positioned to imply any relationship at all.
 *
 * Which nutrient is the caller's choice. Goals can be set for calories, macros and any
 * micronutrient, so restricting this to calories left most of what a user had configured with
 * nothing to compare against.
 */

import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ChartTooltip } from "./chartTheme";
import { AXIS, CHART_MARGIN, GRID, SERIES } from "./theme";
import { formatDateShort, formatNumber, nutrientUnit } from "../../lib/format";
import type { GoalComparisonPoint } from "../../lib/types";

export function GoalVsActualChart({
  points,
  metric = "calories",
}: {
  points: GoalComparisonPoint[];
  metric?: string;
}) {
  const rows = points.map((point) => ({
    bucket: point.bucket,
    actual: point.actual[metric],
    target: point.target[metric],
  }));
  const unit = nutrientUnit(metric);

  return (
    <ResponsiveContainer width="100%" height={260}>
      <ComposedChart data={rows} margin={CHART_MARGIN}>
        <CartesianGrid {...GRID} vertical={false} />
        <XAxis
          dataKey="bucket"
          tickFormatter={formatDateShort}
          tick={AXIS.tick}
          axisLine={{ stroke: AXIS.stroke }}
          tickLine={false}
          minTickGap={24}
        />
        <YAxis
          tick={AXIS.tick}
          axisLine={false}
          tickLine={false}
          width={48}
          tickFormatter={(value: number) => formatNumber(value)}
        />
        <Tooltip
          content={<ChartTooltip labelFormatter={formatDateShort} unit={unit} />}
          cursor={false}
        />
        <Bar
          dataKey="actual"
          name="Logged"
          fill={SERIES[metric as keyof typeof SERIES] ?? SERIES.calories}
          radius={[3, 3, 0, 0]}
          isAnimationActive={false}
        />
        <Line
          type="stepAfter"
          dataKey="target"
          name="Target"
          stroke={SERIES.target}
          strokeWidth={2}
          strokeDasharray="4 3"
          dot={false}
          connectNulls={false}
          isAnimationActive={false}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
