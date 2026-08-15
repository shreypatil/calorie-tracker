/** Log a meal, and browse what has been logged (FR-2, FR-3). */

import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { PageHeading } from "../components/Layout";
import {
  Alert,
  Button,
  Card,
  CardHeader,
  EmptyState,
  ErrorNote,
  Field,
  Input,
  Loading,
  Select,
} from "../components/ui";
import { LogEntryForm } from "./LogEntryForm";
import { useDeleteEntry, useEntries, type EntryFilters } from "../lib/queries";
import { MEAL_LABELS, formatAmount, formatDate, formatNumber, daysAgo, today } from "../lib/format";
import { MEAL_TYPES, type FoodEntry } from "../lib/types";

const PAGE_SIZE = 20;

export function Entries() {
  const [filters, setFilters] = useState<EntryFilters>({
    date_from: daysAgo(29),
    date_to: today(),
    meal_type: "",
    q: "",
    page: 1,
    page_size: PAGE_SIZE,
  });
  // Arriving from "Log a meal" elsewhere in the app opens the form immediately, rather than
  // landing the user on a page where they have to press the same button a second time. A search
  // param rather than router state, so a reload or a shared link still opens it.
  const [params, setParams] = useSearchParams();
  const [showForm, setShowForm] = useState(params.get("log") === "1");
  const formRef = useRef<HTMLDivElement>(null);

  const entries = useEntries(filters);
  const remove = useDeleteEntry();

  useEffect(() => {
    if (params.get("log") !== "1") return;
    formRef.current?.scrollIntoView({ block: "start" });
    // Consumed once: leaving it in the URL would re-open the form on every later navigation.
    params.delete("log");
    setParams(params, { replace: true });
  }, [params, setParams]);

  // Any filter change resets to page 1 — staying on page 4 of a narrower
  // result set would show an empty screen.
  const update = (patch: Partial<EntryFilters>) =>
    setFilters((current) => ({ ...current, ...patch, page: 1 }));

  return (
    <>
      <PageHeading
        title="Entries"
        description="Everything you've logged, filtered by date and meal."
        actions={
          <Button
            variant={showForm ? "secondary" : "primary"}
            onClick={() => setShowForm((open) => !open)}
          >
            {showForm ? "Close" : "Log a meal"}
          </Button>
        }
      />

      {showForm && (
        <div className="mb-5" ref={formRef}>
          <LogEntryForm onLogged={() => setShowForm(false)} />
        </div>
      )}

      <Card className="mb-5 p-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="From">
            <Input
              type="date"
              value={filters.date_from ?? ""}
              max={filters.date_to}
              onChange={(e) => update({ date_from: e.target.value })}
            />
          </Field>
          <Field label="To">
            <Input
              type="date"
              value={filters.date_to ?? ""}
              min={filters.date_from}
              onChange={(e) => update({ date_to: e.target.value })}
            />
          </Field>
          <Field label="Meal">
            <Select
              value={filters.meal_type}
              onChange={(e) => update({ meal_type: e.target.value as EntryFilters["meal_type"] })}
            >
              <option value="">All meals</option>
              {MEAL_TYPES.map((meal) => (
                <option key={meal} value={meal}>
                  {MEAL_LABELS[meal]}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Food name">
            <Input
              placeholder="Search"
              value={filters.q ?? ""}
              onChange={(e) => update({ q: e.target.value })}
            />
          </Field>
        </div>
      </Card>

      <Card>
        <CardHeader
          title="Logged items"
          subtitle={
            entries.data
              ? `${formatNumber(entries.data.total)} ${entries.data.total === 1 ? "entry" : "entries"}`
              : undefined
          }
        />

        {entries.isLoading ? (
          <Loading />
        ) : entries.error ? (
          <ErrorNote error={entries.error} />
        ) : entries.data?.items.length === 0 ? (
          <EmptyState
            title="Nothing here"
            description="No entries match these filters. Widen the date range, or log a meal to get started."
            action={
              <Button variant="primary" onClick={() => setShowForm(true)}>
                Log a meal
              </Button>
            }
          />
        ) : (
          <>
            {remove.error && (
              <div className="px-5 pt-4">
                <Alert>Could not delete that entry. Try again.</Alert>
              </div>
            )}
            <EntryTable
              entries={entries.data!.items}
              onDelete={(id) => remove.mutate(id)}
              deletingId={remove.isPending ? (remove.variables as string) : null}
            />
            <Pagination
              page={entries.data!.page}
              pageSize={entries.data!.page_size}
              total={entries.data!.total}
              hasNext={entries.data!.has_next}
              onChange={(page) => setFilters((current) => ({ ...current, page }))}
            />
          </>
        )}
      </Card>
    </>
  );
}

function EntryTable({
  entries,
  onDelete,
  deletingId,
}: {
  entries: FoodEntry[];
  onDelete: (id: string) => void;
  deletingId: string | null;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[46rem] border-collapse text-[13px]">
        <thead>
          <tr className="border-b border-rule">
            <th className="eyebrow px-5 py-2 text-left font-normal">Date</th>
            <th className="eyebrow px-3 py-2 text-left font-normal">Meal</th>
            <th className="eyebrow px-3 py-2 text-left font-normal">Food</th>
            <th className="eyebrow px-3 py-2 text-right font-normal">Calories</th>
            <th className="eyebrow px-3 py-2 text-right font-normal">P / C / F</th>
            <th className="px-5 py-2" />
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => (
            <tr key={entry.id} className="border-b border-rule-soft last:border-0">
              <td className="whitespace-nowrap px-5 py-2.5 font-mono tabular text-ink-muted">
                {formatDate(entry.consumed_on)}
              </td>
              <td className="whitespace-nowrap px-3 py-2.5">{MEAL_LABELS[entry.meal_type]}</td>
              <td className="px-3 py-2.5">
                {entry.food_name}
                <span className="ml-1.5 text-ink-muted">
                  {formatAmount(entry.quantity)} {entry.unit}
                </span>
              </td>
              <td className="whitespace-nowrap px-3 py-2.5 text-right font-mono tabular">
                {formatNumber(entry.calories)}
              </td>
              <td className="whitespace-nowrap px-3 py-2.5 text-right font-mono tabular text-ink-muted">
                {formatAmount(entry.protein_g)} / {formatAmount(entry.carbs_g)} /{" "}
                {formatAmount(entry.fat_g)}
              </td>
              <td className="px-5 py-2.5 text-right">
                <button
                  className="text-[13px] text-ink-muted underline hover:text-danger disabled:opacity-50"
                  disabled={deletingId === entry.id}
                  onClick={() => onDelete(entry.id)}
                >
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Pagination({
  page,
  pageSize,
  total,
  hasNext,
  onChange,
}: {
  page: number;
  pageSize: number;
  total: number;
  hasNext: boolean;
  onChange: (page: number) => void;
}) {
  const first = (page - 1) * pageSize + 1;
  const last = Math.min(page * pageSize, total);

  return (
    <div className="flex items-center justify-between gap-3 border-t border-rule px-5 py-3">
      <p className="text-[13px] text-ink-muted">
        <span className="font-mono tabular">
          {formatNumber(first)}–{formatNumber(last)}
        </span>{" "}
        of <span className="font-mono tabular">{formatNumber(total)}</span>
      </p>
      <div className="flex gap-2">
        <Button disabled={page <= 1} onClick={() => onChange(page - 1)}>
          Previous
        </Button>
        <Button disabled={!hasNext} onClick={() => onChange(page + 1)}>
          Next
        </Button>
      </div>
    </div>
  );
}
