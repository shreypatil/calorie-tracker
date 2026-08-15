/**
 * What the parser understood, in plain terms.
 *
 * This is the honest part of the feature: before anything is saved, the user
 * sees the reading that produced these rows, and can correct the two things
 * most often wrong — the date order and the meal fallback — in one click each.
 */

import { Field, Select, Value } from "../ui";
import { nutrientLabel } from "../../lib/format";
import {
  DATE_FORMAT_LABELS,
  MEAL_TYPES,
  type DateFormat,
  type MealType,
  type PdfImportPreview,
} from "../../lib/types";
import { MEAL_LABELS } from "../../lib/format";

const FIELD_LABELS: Record<string, string> = {
  consumed_on: "date",
  meal_type: "meal",
  food_name: "food",
  quantity: "quantity",
  unit: "unit",
};

function describe(target: string): string {
  return FIELD_LABELS[target] ?? nutrientLabel(target).toLowerCase();
}

export function MappingSummary({
  preview,
  busy,
  onDateFormatChange,
  onDefaultMealChange,
}: {
  preview: PdfImportPreview;
  busy: boolean;
  onDateFormatChange: (value: DateFormat) => void;
  onDefaultMealChange: (value: MealType) => void;
}) {
  const { summary, mapping, source_kind } = preview;

  return (
    <div className="border-b border-rule px-5 py-4">
      <p className="text-[14px]">
        Read <Value className="font-medium">{summary.row_count}</Value> rows from{" "}
        <Value>{summary.page_count}</Value> {summary.page_count === 1 ? "page" : "pages"} of{" "}
        <span className="font-medium">{summary.filename}</span>.
        {source_kind === "prose" && " No table was found, so entries were read from the text."}
      </p>

      {mapping.columns.length > 0 && (
        <p className="mt-1.5 text-[13px] text-ink-muted">
          Columns:{" "}
          {mapping.columns.map((column, index) => (
            <span key={column.source}>
              {index > 0 && ", "}
              <span className="font-mono">{column.source}</span> → {describe(column.target)}
            </span>
          ))}
          .
        </p>
      )}

      {mapping.basis === "per_100g" && (
        <p className="mt-1.5 text-[13px] text-ink-soft">
          Values are per 100g and were scaled by the{" "}
          <span className="font-mono">{mapping.quantity_column}</span> column.
        </p>
      )}

      {mapping.notes && <p className="mt-1.5 text-[13px] text-ink-muted">{mapping.notes}</p>}

      <div className="mt-4 flex flex-wrap items-end gap-4">
        <Field label="Dates read as" className="w-56">
          <Select
            value={mapping.date_format}
            disabled={busy}
            onChange={(event) => onDateFormatChange(event.target.value as DateFormat)}
          >
            {Object.entries(DATE_FORMAT_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>
        </Field>

        <Field label="Rows with no meal" className="w-56">
          <Select
            value={mapping.default_meal_type ?? ""}
            disabled={busy}
            onChange={(event) => onDefaultMealChange(event.target.value as MealType)}
          >
            {/* With a meal column in the file this control does nothing, and a
                real meal shown as selected would claim otherwise. */}
            {mapping.default_meal_type === null && (
              <option value="">Not needed — file has meals</option>
            )}
            {MEAL_TYPES.map((meal) => (
              <option key={meal} value={meal}>
                {MEAL_LABELS[meal]}
              </option>
            ))}
          </Select>
        </Field>

        <p className="pb-1.5 text-[13px] text-ink-muted">
          Changing either re-reads the file.
        </p>
      </div>

      <div className="mt-4 flex flex-wrap gap-x-5 gap-y-1 border-t border-rule-soft pt-3 text-[13px]">
        <span>
          <Value className="font-medium text-good">{summary.ready}</Value> ready
        </span>
        <span>
          <Value className="font-medium text-warn">{summary.needs_review}</Value> need a look
        </span>
        <span>
          <Value className="font-medium text-danger">{summary.invalid}</Value> could not be read
        </span>
        {summary.duplicates > 0 && (
          <span className="text-ink-muted">
            <Value>{summary.duplicates}</Value> look like entries you already have
          </span>
        )}
      </div>
    </div>
  );
}
