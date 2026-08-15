/** Macronutrient grams per bucket, stacked (FR-4). */

import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ChartTooltip } from "./chartTheme";
import { AXIS, CHART_MARGIN, GRID, SERIES } from "./theme";
import { formatDateShort, formatNumber } from "../../lib/format";
import { MACROS, type MacroPoint } from "../../lib/types";

const LABELS: Record<string, string> = {
  protein_g: "Protein",
  carbs_g: "Carbs",
  fat_g: "Fat",
};

export function MacroChart({ points }: { points: MacroPoint[] }) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={points} margin={CHART_MARGIN}>
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
        <Tooltip content={<ChartTooltip labelFormatter={formatDateShort} unit="g" />} cursor={false} />
        {MACROS.map((macro, index) => (
          <Bar
            key={macro}
            dataKey={macro}
            name={LABELS[macro]}
            stackId="macros"
            fill={SERIES[macro]}
            // A hairline of surface between segments keeps the boundary legible
            // without a border that would darken the stack.
            stroke="#ffffff"
            strokeWidth={1}
            radius={index === MACROS.length - 1 ? [3, 3, 0, 0] : 0}
            isAnimationActive={false}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}
