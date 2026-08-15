/**
 * Reading a photo into the log form (FR-5).
 *
 * Two buttons rather than one, because the two jobs are genuinely different and the app is
 * more honest when it says so. Scanning a **label** is transcription — the figures exist on
 * the packet and are checked against the model's own reading of it. Photographing a **meal**
 * is estimation, with nothing to check against. Telling the user which they are getting is
 * the whole reason the modes are separate.
 *
 * A single food fills the form directly. Several become a draft table, because a plate is
 * three foods and averaging them into one row throws away exactly the detail that makes the
 * macros worth logging.
 */

import { useRef, useState } from "react";

import { ApiError } from "../../lib/api";
import { useAnalyzeImage, useCommitPhotoRows } from "../../lib/queries";
import {
  MICRONUTRIENTS,
  type DraftRow,
  type MealType,
  type PhotoDraft,
  type PhotoKind,
} from "../../lib/types";
import { MealDraftTable, type DraftRowView } from "../MealDraftTable";
import { Alert, Button } from "../ui";

const KIND_LABEL: Record<PhotoKind, string> = {
  label: "Read from the packet and checked against it",
  meal: "Estimated — portions are a judgement, not a measurement",
};

/**
 * Issues that every row shares describe the draft, not any particular row — "estimated from a
 * photo" repeated down a plate of three foods is noise that buries the row-specific warnings
 * worth reading. Those are lifted out and shown once.
 */
function splitIssues(rows: DraftRow[]): {
  shared: string[];
  perRow: string[][];
} {
  const messages = rows.map((row) => row.issues.map((issue) => issue.message));
  const shared =
    rows.length > 1 ? messages[0].filter((m) => messages.every((r) => r.includes(m))) : [];
  return {
    shared,
    perRow: messages.map((row) => row.filter((m) => !shared.includes(m))),
  };
}

/**
 * Every nutrient the extraction produced travels into the editable row, not just the four shown
 * as columns — the expander edits micronutrients too, and dropping them here would silently
 * discard values the model did read off the plate.
 */
function toView(row: DraftRow): DraftRowView {
  const entry = row.entry!;
  return {
    food_name: entry.food_name,
    meal_type: entry.meal_type,
    quantity: entry.quantity,
    unit: entry.unit,
    calories: entry.calories,
    protein_g: entry.protein_g,
    carbs_g: entry.carbs_g,
    fat_g: entry.fat_g,
    ...Object.fromEntries(
      MICRONUTRIENTS.map((name) => [name, entry[name]]).filter(([, value]) => value != null),
    ),
  };
}

export function ScanControl({
  mealType,
  consumedOn,
  onSingleResult,
  onCommitted,
}: {
  mealType: MealType;
  consumedOn: string;
  /** One food: hand it straight to the form rather than making the user retype it. */
  onSingleResult: (row: DraftRow) => void;
  onCommitted: () => void;
}) {
  const analyze = useAnalyzeImage();
  const commit = useCommitPhotoRows();
  const inputRef = useRef<HTMLInputElement>(null);
  const kindRef = useRef<PhotoKind>("label");

  const [draft, setDraft] = useState<PhotoDraft | null>(null);
  const [rows, setRows] = useState<DraftRowView[]>([]);

  const pick = (kind: PhotoKind) => {
    kindRef.current = kind;
    inputRef.current?.click();
  };

  const onFile = (file: File | undefined) => {
    if (!file) return;
    setDraft(null);
    analyze.mutate(
      {
        file,
        kind: kindRef.current,
        meal_type: mealType,
        consumed_on: consumedOn,
      },
      {
        onSuccess: (result) => {
          const usable = result.rows.filter((row) => row.entry);
          if (usable.length === 1) {
            onSingleResult(usable[0]);
            return;
          }
          setDraft(result);
          setRows(usable.map(toView));
        },
      },
    );
    // Clear the input, or re-picking the same file fires no change event.
    if (inputRef.current) inputRef.current.value = "";
  };

  const update = (index: number, patch: Partial<DraftRowView>) =>
    setRows((current) =>
      current.map((row, position) => (position === index ? { ...row, ...patch } : row)),
    );

  const addAll = () => {
    if (!draft) return;
    const entries = draft.rows
      .filter((row) => row.entry)
      .map((row, index) => ({ ...row.entry!, ...rows[index] }));
    commit.mutate(entries, {
      onSuccess: () => {
        setDraft(null);
        setRows([]);
        onCommitted();
      },
    });
  };

  const error = analyze.error ?? commit.error;
  const issues = splitIssues(draft?.rows.filter((row) => row.entry) ?? []);

  return (
    <div className="border-b border-rule px-5 py-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="eyebrow">From a photo</span>
        <Button type="button" onClick={() => pick("label")} disabled={analyze.isPending}>
          Scan a label
        </Button>
        <Button type="button" onClick={() => pick("meal")} disabled={analyze.isPending}>
          Estimate a meal
        </Button>
        {analyze.isPending && (
          <span className="text-[13px] text-ink-muted">Reading the photo…</span>
        )}
        <input
          ref={inputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          className="sr-only"
          aria-label="Photo to analyse"
          onChange={(event) => onFile(event.target.files?.[0])}
        />
      </div>

      {error && (
        <div className="mt-3">
          <Alert>
            {error instanceof ApiError ? error.message : "That photo could not be read."}
          </Alert>
        </div>
      )}

      {draft && rows.length > 0 && (
        <div className="mt-4 rounded-md border border-ink/25 bg-surface px-4 py-3">
          <div className="flex flex-wrap items-baseline justify-between gap-2 pb-2">
            <span className="eyebrow">Draft · nothing saved yet</span>
            <span className="text-[13px] text-ink-soft">{KIND_LABEL[draft.kind]}</span>
          </div>

          <MealDraftTable
            rows={rows}
            editable
            onChange={update}
            issuesFor={(index) => issues.perRow[index] ?? []}
          />

          {[...issues.shared, draft.notes].filter(Boolean).map((note) => (
            <p key={note} className="mt-2 text-[12px] text-ink-muted">
              {note}
            </p>
          ))}

          <div className="mt-3 flex items-center gap-2 border-t border-rule pt-3">
            <Button type="button" variant="primary" onClick={addAll} disabled={commit.isPending}>
              {commit.isPending ? "Saving…" : `Add all ${rows.length}`}
            </Button>
            <Button type="button" onClick={() => setDraft(null)} disabled={commit.isPending}>
              Discard
            </Button>
            <span className="text-[12px] text-ink-muted">
              Edit anything that looks wrong first.
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
