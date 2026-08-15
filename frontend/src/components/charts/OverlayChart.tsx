/**
 * Several nutrients on one time axis.
 *
 * The hard part here is not drawing the lines, it is that the selected nutrients rarely share a
 * unit. Calories sit near 2,000 while protein sits near 100 and iron near 14 — put them on one
 * axis and everything except calories flattens onto the floor, which looks like a working chart
 * and tells the reader nothing. So metrics are grouped into unit families and given up to two
 * axes; the caller refuses a third family rather than drawing something misleading.
 *
 * Colour comes from the slot, not the nutrient — see `OVERLAY_SERIES` for why that matters —
 * and each slot also carries a dash pattern, so the series remain tellable apart in greyscale or
 * with any colour-vision deficiency.
 */

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { ChartTooltip } from "./chartTheme";
import { AXIS, CHART_MARGIN, GRID, OVERLAY_DASHES, OVERLAY_SERIES, unitFamilies } from "./theme";
import { formatDateShort, formatNumber, nutrientLabel, nutrientUnit } from "../../lib/format";

export interface OverlayPoint {
  bucket: string;
  [metric: string]: string | number;
}

export function OverlayChart({ points, metrics }: { points: OverlayPoint[]; metrics: string[] }) {
  const families = unitFamilies(metrics);
  const axisFor = (metric: string) => (nutrientUnit(metric) === families[0] ? "left" : "right");

  return (
    <ResponsiveContainer width="100%" height={300}>
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
          yAxisId="left"
          tick={AXIS.tick}
          axisLine={false}
          tickLine={false}
          width={56}
          tickFormatter={(value: number) => formatNumber(value)}
        />

        {families.length > 1 && (
          <YAxis
            yAxisId="right"
            orientation="right"
            tick={AXIS.tick}
            axisLine={false}
            tickLine={false}
            width={56}
            tickFormatter={(value: number) => formatNumber(value)}
          />
        )}

        <Tooltip
          content={<ChartTooltip labelFormatter={formatDateShort} />}
          cursor={{ stroke: AXIS.stroke }}
        />

        {metrics.map((metric, index) => (
          <Line
            key={metric}
            yAxisId={axisFor(metric)}
            type="monotone"
            dataKey={metric}
            name={nutrientLabel(metric)}
            stroke={OVERLAY_SERIES[index % OVERLAY_SERIES.length]}
            strokeDasharray={OVERLAY_DASHES[index % OVERLAY_DASHES.length]}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, strokeWidth: 2, stroke: "#ffffff" }}
            isAnimationActive={false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
