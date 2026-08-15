/** Calorie intake over time, against the goal in force (FR-4). */

import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ChartTooltip } from "./chartTheme";
import { AXIS, CHART_MARGIN, GRID, SERIES } from "./theme";
import { formatDateShort, formatNumber } from "../../lib/format";
import type { TrendPoint } from "../../lib/types";

export function TrendChart({
  points,
  target,
  targetLabel,
}: {
  points: TrendPoint[];
  target?: number | null;
  targetLabel?: string;
}) {
  // Recharts scales the axis to the data alone, so a target above every logged
  // day — the normal case when you are under your goal — would be drawn off the
  // top and silently vanish. Include it in the domain, rounded up to a round
  // number so the axis reads 2,400 rather than 2,376.
  const upperBound = (dataMax: number) => {
    const headroom = Math.max(dataMax, target ?? 0) * 1.08;
    const step = headroom > 2000 ? 200 : 100;
    return Math.ceil(headroom / step) * step;
  };

  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={points} margin={CHART_MARGIN}>
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
          domain={[0, upperBound]}
          tickFormatter={(value: number) => formatNumber(value)}
        />
        {/* The target is context, not a series: dashed and grey so the data leads. */}
        {target ? (
          <ReferenceLine
            y={target}
            stroke={SERIES.target}
            strokeDasharray="4 3"
            label={{
              value: targetLabel ?? `Target ${formatNumber(target)}`,
              position: "insideTopRight",
              fill: SERIES.target,
              fontSize: 11,
              fontFamily: "IBM Plex Mono, monospace",
            }}
          />
        ) : null}
        <Tooltip
          content={<ChartTooltip labelFormatter={formatDateShort} unit="kcal" />}
          cursor={{ stroke: AXIS.stroke }}
        />
        <Line
          type="monotone"
          dataKey="calories"
          name="Calories"
          stroke={SERIES.calories}
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4, strokeWidth: 2, stroke: "#ffffff" }}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
