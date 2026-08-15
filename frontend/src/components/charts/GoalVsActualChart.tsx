/**
 * Calories logged against the target that was in force (FR-4).
 *
 * Both series are calories, so they share one axis — a second scale would let
 * the two lines be positioned to imply any relationship at all.
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
import { formatDateShort, formatNumber } from "../../lib/format";
import type { GoalComparisonPoint } from "../../lib/types";

export function GoalVsActualChart({ points }: { points: GoalComparisonPoint[] }) {
  const rows = points.map((point) => ({
    bucket: point.bucket,
    actual: point.actual.calories,
    target: point.target.calories,
  }));

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
        <Tooltip content={<ChartTooltip labelFormatter={formatDateShort} unit="kcal" />} cursor={false} />
        <Bar
          dataKey="actual"
          name="Logged"
          fill={SERIES.calories}
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
