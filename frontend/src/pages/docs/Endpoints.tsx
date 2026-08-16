/**
 * The API surface, fetched live from `/openapi.json`.
 *
 * Not generated at build time and not written by hand: FastAPI derives that spec from the route
 * signatures themselves, so fetching it at render is the freshest possible source. An endpoint
 * renamed a minute ago is already correct here, which no build step could promise.
 */

import { useQuery } from "@tanstack/react-query";

import { Alert, Card, CardHeader, Loading, Value } from "../../components/ui";
import { cx } from "../../lib/cx";

interface Operation {
  summary?: string;
  description?: string;
  tags?: string[];
  parameters?: { name: string; in: string; required?: boolean }[];
  requestBody?: unknown;
  security?: unknown[];
}

interface Spec {
  info: { title: string; version: string };
  paths: Record<string, Record<string, Operation>>;
}

const METHOD_STYLES: Record<string, string> = {
  get: "bg-accent-soft text-accent",
  post: "bg-carbs/15 text-carbs",
  patch: "bg-protein/15 text-protein",
  delete: "bg-danger-soft text-danger",
};

function MethodBadge({ method }: { method: string }) {
  return (
    <span
      className={cx(
        "inline-block rounded px-1.5 py-0.5 font-mono text-[11px] font-medium uppercase",
        METHOD_STYLES[method] ?? "bg-rule-soft text-ink-soft",
      )}
    >
      {method}
    </span>
  );
}

export function Endpoints() {
  const spec = useQuery({
    queryKey: ["openapi"],
    queryFn: async (): Promise<Spec> => {
      const response = await fetch("/openapi.json");
      if (!response.ok) throw new Error(`The API returned ${response.status}.`);
      return response.json();
    },
    staleTime: 60_000,
  });

  if (spec.isLoading) return <Loading label="Reading the API spec" />;
  if (spec.error || !spec.data) {
    return (
      <Alert>
        Could not read <span className="font-mono">/openapi.json</span>. The API needs to be running
        — this page reads the live spec rather than a stored copy.
      </Alert>
    );
  }

  // Group by tag, which is the router each route belongs to.
  const groups = new Map<string, { path: string; method: string; operation: Operation }[]>();
  for (const [path, operations] of Object.entries(spec.data.paths)) {
    for (const [method, operation] of Object.entries(operations)) {
      const tag = operation.tags?.[0] ?? "other";
      if (!groups.has(tag)) groups.set(tag, []);
      groups.get(tag)!.push({ path, method, operation });
    }
  }

  const total = [...groups.values()].reduce((sum, items) => sum + items.length, 0);

  return (
    <>
      <p className="mb-5 text-[13px] text-ink-muted">
        Read live from <span className="font-mono">/openapi.json</span>, which FastAPI generates
        from the route signatures — so this list is the API, not a description of it.{" "}
        <Value>{total}</Value> operations across <Value>{groups.size}</Value> areas. The interactive
        version is at <span className="font-mono">/docs</span> on the API.
      </p>

      {[...groups.entries()].sort().map(([tag, items]) => (
        <Card key={tag} className="mb-5">
          <CardHeader title={tag} subtitle={`${items.length} operations`} />
          <table className="w-full text-[13px]">
            <tbody>
              {items
                .sort((a, b) => a.path.localeCompare(b.path))
                .map(({ path, method, operation }) => (
                  <tr
                    key={`${method}-${path}`}
                    className="border-b border-rule-soft align-top last:border-0"
                  >
                    <td className="py-2.5 pr-3 pl-5 whitespace-nowrap">
                      <MethodBadge method={method} />
                    </td>
                    <td className="py-2.5 pr-3 font-mono text-[12px] whitespace-nowrap">{path}</td>
                    <td className="py-2.5 pr-5">
                      <p>{operation.summary ?? "—"}</p>
                      {operation.description && (
                        <p className="mt-1 text-[12px] whitespace-pre-line text-ink-muted">
                          {operation.description.trim()}
                        </p>
                      )}
                      {operation.parameters && operation.parameters.length > 0 && (
                        <p className="mt-1.5 text-[12px] text-ink-muted">
                          <span className="eyebrow">Params</span>{" "}
                          {operation.parameters
                            .map((p) => `${p.name}${p.required ? "*" : ""}`)
                            .join(", ")}
                        </p>
                      )}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </Card>
      ))}
    </>
  );
}
