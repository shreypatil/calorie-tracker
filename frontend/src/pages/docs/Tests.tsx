/**
 * The test inventory, taken from pytest and the test sources.
 *
 * Two counts are shown deliberately. The browsable list has one entry per `def test_*`; the total
 * pytest reports is higher because `@parametrize` expands into a case per argument set. Showing
 * only the first would quietly disagree with what `make test` prints.
 *
 * The manual table is empty on purpose — it records testing actually performed, and pre-filling it
 * would make it a work of fiction.
 */

import { Fragment, useState } from "react";

import { Card, CardHeader, EmptyState, Value } from "../../components/ui";
import { cx } from "../../lib/cx";
import tests from "../../docs/generated/tests.json";

const KIND_LABEL: Record<string, string> = {
  functional: "Functional",
  unit: "Unit",
  browser: "Browser",
  check: "Check",
};

function KindTag({ kind }: { kind: string }) {
  return (
    <span
      className={cx(
        "inline-block rounded px-1.5 py-0.5 text-[11px] whitespace-nowrap",
        kind === "functional" ? "bg-accent-soft text-accent" : "bg-rule-soft text-ink-soft",
      )}
    >
      {KIND_LABEL[kind] ?? kind}
    </span>
  );
}

export function Tests() {
  const [open, setOpen] = useState<string | null>(null);

  const functional = tests.files.reduce(
    (sum, file) => sum + file.cases.filter((c) => c.kind === "functional").length,
    0,
  );

  return (
    <>
      <p className="mb-5 text-[13px] text-ink-muted">
        Taken from pytest and the test sources. <Value>{tests.collected}</Value> cases collected
        from <Value>{tests.total}</Value> test functions across <Value>{tests.files.length}</Value>{" "}
        files — the difference is parametrised tests expanding into one case per argument set. Of
        the functions, <Value>{functional}</Value> drive the API over HTTP and the rest exercise
        units directly. The whole suite runs against the deterministic stub provider, so it needs no
        API key, no network and no quota.
      </p>

      <Card className="mb-5">
        <CardHeader title="Automated — backend" subtitle="Click a file to see its cases" />
        <table className="w-full text-[13px]">
          <thead>
            <tr className="border-b border-rule">
              <th className="eyebrow px-5 py-2 text-left font-normal">File</th>
              <th className="eyebrow px-5 py-2 text-left font-normal">Covers</th>
              <th className="eyebrow px-5 py-2 text-right font-normal">Cases</th>
            </tr>
          </thead>
          <tbody>
            {tests.files.map((file) => (
              <Fragment key={file.file}>
                <tr
                  className="cursor-pointer border-b border-rule-soft align-top last:border-0 hover:bg-paper"
                  onClick={() => setOpen(open === file.file ? null : file.file)}
                >
                  <td className="px-5 py-2.5 font-mono text-[12px] whitespace-nowrap">
                    {open === file.file ? "−" : "+"} {file.file.replace("backend/tests/", "")}
                  </td>
                  <td className="py-2.5 pr-5 text-ink-muted">{file.purpose || "—"}</td>
                  <td className="px-5 py-2.5 text-right">
                    <Value>{file.collected}</Value>
                  </td>
                </tr>
                {open === file.file && (
                  <tr className="border-b border-rule-soft">
                    <td colSpan={3} className="px-5 py-3">
                      <ul className="space-y-1.5">
                        {file.cases.map((testCase) => (
                          <li key={testCase.name} className="flex flex-wrap items-baseline gap-2">
                            <KindTag kind={testCase.kind} />
                            <span className="font-mono text-[12px]">{testCase.name}</span>
                            {testCase.description && (
                              <span className="text-[12px] text-ink-muted">
                                {testCase.description}
                              </span>
                            )}
                          </li>
                        ))}
                      </ul>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t-2 border-ink">
              <td className="eyebrow px-5 py-2.5" colSpan={2}>
                Total
              </td>
              <td className="px-5 py-2.5 text-right">
                <Value className="font-semibold">{tests.collected}</Value>
              </td>
            </tr>
          </tfoot>
        </table>
      </Card>

      <Card className="mb-5">
        <CardHeader title="Automated — frontend" subtitle="Run by `make test` and on demand" />
        <table className="w-full text-[13px]">
          <tbody>
            {tests.frontend.map((item) => (
              <tr key={item.file} className="border-b border-rule-soft align-top last:border-0">
                <td className="px-5 py-2.5 font-mono text-[12px] whitespace-nowrap">{item.file}</td>
                <td className="py-2.5 pr-3">
                  <KindTag kind={item.kind} />
                </td>
                <td className="py-2.5 pr-5 text-ink-muted">{item.description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <Card>
        <CardHeader
          title="Manual and integration testing"
          subtitle="Verification performed by hand, including against a live AI provider"
        />
        {tests.manual.length === 0 ? (
          <EmptyState
            title="Nothing recorded yet"
            description={`Add entries to the "manual" array in backend/scripts/generate_docs.py and run make docs. Columns: ${tests.manual_columns.join(", ")}.`}
          />
        ) : (
          <table className="w-full text-[13px]">
            <thead>
              <tr className="border-b border-rule">
                {tests.manual_columns.map((column) => (
                  <th key={column} className="eyebrow px-5 py-2 text-left font-normal capitalize">
                    {column}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(tests.manual as Record<string, string>[]).map((row, index) => (
                <tr key={index} className="border-b border-rule-soft align-top last:border-0">
                  {tests.manual_columns.map((column) => (
                    <td key={column} className="px-5 py-2.5">
                      {row[column] ?? "—"}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </>
  );
}
