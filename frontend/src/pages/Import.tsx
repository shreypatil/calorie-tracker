/**
 * Import a PDF food diary (FR-8).
 *
 * Upload → see what was understood → correct it → import. Nothing reaches the
 * database until the last step, and every import can be undone as a unit.
 */

import { useState } from "react";
import { PageHeading } from "../components/Layout";
import {
  Alert,
  Button,
  Card,
  CardHeader,
  EmptyState,
  Field,
  Input,
  Loading,
  Value,
} from "../components/ui";
import { MappingSummary } from "../components/import/MappingSummary";
import { ReviewTable } from "../components/import/ReviewTable";
import {
  useCommitImport,
  useImportHistory,
  usePreviewImport,
  useUndoImport,
} from "../lib/queries";
import { ApiError } from "../lib/api";
import { formatDate, formatNumber } from "../lib/format";
import type { DateFormat, MealType, PdfImportPreview } from "../lib/types";

export function Import() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<PdfImportPreview | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [imported, setImported] = useState<{ count: number } | null>(null);

  const parse = usePreviewImport();
  const commit = useCommitImport();
  const history = useImportHistory();
  const undo = useUndoImport();

  function selectImportable(next: PdfImportPreview) {
    // Default to everything that can be imported. Rows needing a look are
    // included but visibly flagged — excluding them by default would hide
    // most of a messy diary behind a step the user might not notice.
    setSelected(new Set(next.rows.filter((row) => row.entry !== null).map((row) => row.index)));
  }

  async function runPreview(chosen: File, overrides: Record<string, string> = {}) {
    setError(null);
    setImported(null);
    try {
      const next = await parse.mutateAsync({ file: chosen, ...overrides });
      setPreview(next);
      selectImportable(next);
    } catch (err) {
      setPreview(null);
      setError(
        err instanceof ApiError
          ? err.message
          : "Could not read that file. Check it is a PDF and try again.",
      );
    }
  }

  async function handleFile(chosen: File | null) {
    setFile(chosen);
    setPreview(null);
    if (chosen) await runPreview(chosen);
  }

  async function reread(overrides: Record<string, string>) {
    if (file) await runPreview(file, overrides);
  }

  async function handleImport() {
    if (!preview) return;
    const entries = preview.rows
      .filter((row) => selected.has(row.index) && row.entry)
      .map((row) => row.entry);

    try {
      const created = await commit.mutateAsync({
        entries: entries as unknown[],
        filename: preview.summary.filename,
      });
      setImported({ count: created.length });
      setPreview(null);
      setFile(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save those entries.");
    }
  }

  const selectedCount = selected.size;

  return (
    <>
      <PageHeading
        title="Import"
        description="Upload a PDF food diary. You'll see everything it read before anything is saved."
      />

      <div className="space-y-5">
        <Card className="p-5">
          <Field
            label="PDF file"
            className="max-w-md"
            hint="Exported from a tracking app or a spreadsheet. Scanned pages aren't supported yet."
          >
            <Input
              type="file"
              accept="application/pdf,.pdf"
              onChange={(event) => handleFile(event.target.files?.[0] ?? null)}
            />
          </Field>

          {error && (
            <div className="mt-4 max-w-2xl">
              <Alert>{error}</Alert>
            </div>
          )}

          {imported && (
            <div className="mt-4 max-w-2xl">
              <Alert tone="info">
                Imported <Value className="font-medium">{imported.count}</Value> entries. You can
                undo it below.
              </Alert>
            </div>
          )}
        </Card>

        {parse.isPending && (
          <Card>
            <Loading label="Reading the file" />
          </Card>
        )}

        {preview && !parse.isPending && (
          <Card>
            <MappingSummary
              preview={preview}
              busy={parse.isPending}
              onDateFormatChange={(value: DateFormat) => reread({ date_format: value })}
              onDefaultMealChange={(value: MealType) => reread({ default_meal_type: value })}
            />

            {preview.rows.length === 0 ? (
              <EmptyState
                title="No entries found"
                description="Nothing in this PDF looked like a food diary. Try a different export."
              />
            ) : (
              <>
                <ReviewTable
                  rows={preview.rows}
                  selected={selected}
                  onToggle={(index) =>
                    setSelected((current) => {
                      const next = new Set(current);
                      if (next.has(index)) next.delete(index);
                      else next.add(index);
                      return next;
                    })
                  }
                  onToggleAll={(checked) =>
                    setSelected(
                      checked
                        ? new Set(
                            preview.rows.filter((row) => row.entry).map((row) => row.index),
                          )
                        : new Set(),
                    )
                  }
                />

                <div className="flex flex-wrap items-center justify-between gap-3 border-t border-rule px-5 py-3">
                  <p className="text-[13px] text-ink-muted">
                    <Value>{selectedCount}</Value> of{" "}
                    <Value>{preview.summary.row_count}</Value> rows selected
                  </p>
                  <Button
                    variant="primary"
                    disabled={selectedCount === 0 || commit.isPending}
                    onClick={handleImport}
                  >
                    {commit.isPending
                      ? "Importing…"
                      : `Import ${formatNumber(selectedCount)} ${
                          selectedCount === 1 ? "entry" : "entries"
                        }`}
                  </Button>
                </div>
              </>
            )}
          </Card>
        )}

        <Card>
          <CardHeader title="Past imports" subtitle="Undo removes every entry an import created." />
          {history.isLoading ? (
            <Loading />
          ) : history.data?.items.length === 0 ? (
            <EmptyState
              title="Nothing imported yet"
              description="Imports you make will be listed here, each with its own undo."
            />
          ) : (
            <table className="w-full border-collapse text-[13px]">
              <tbody>
                {history.data?.items.map((batch) => (
                  <tr key={batch.id} className="border-b border-rule-soft last:border-0">
                    <td className="px-5 py-2.5">{batch.filename}</td>
                    <td className="whitespace-nowrap px-3 py-2.5 font-mono tabular text-ink-muted">
                      {formatDate(batch.created_at.slice(0, 10))}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5 text-right font-mono tabular">
                      {formatNumber(batch.entries_remaining)}
                      <span className="ml-1 text-ink-muted">
                        {batch.entries_remaining === batch.row_count
                          ? "entries"
                          : `of ${formatNumber(batch.row_count)} left`}
                      </span>
                    </td>
                    <td className="px-5 py-2.5 text-right">
                      <button
                        className="text-[13px] text-ink-muted underline hover:text-danger disabled:opacity-50"
                        disabled={undo.isPending}
                        onClick={() => undo.mutate(batch.id)}
                      >
                        Undo
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      </div>
    </>
  );
}
