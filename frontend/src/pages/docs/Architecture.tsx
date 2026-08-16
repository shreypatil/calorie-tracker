/**
 * Layers, invariants and dependencies.
 *
 * Versions come from `pyproject.toml` and `package.json` — the manifests that actually install
 * them — so this page cannot claim a version the project does not use.
 */

import { Card, CardHeader, Value } from "../../components/ui";
import architecture from "../../docs/generated/architecture.json";

export function Architecture() {
  return (
    <>
      <p className="mb-5 text-[13px] text-ink-muted">
        The shape of the codebase and the rules that hold it together. Dependency versions are read
        from the manifests, not transcribed.
      </p>

      <Card className="mb-5">
        <CardHeader
          title="Architectural invariants"
          subtitle="Break these and the design stops working — they are not stylistic"
        />
        <ol className="divide-y divide-rule-soft">
          {architecture.invariants.map((invariant, index) => (
            <li key={invariant.title} className="flex gap-4 px-5 py-3">
              <Value className="text-ink-muted">{index + 1}</Value>
              <div>
                <p className="text-[13px] font-medium">{invariant.title}</p>
                <p className="mt-1 text-[13px] text-ink-muted">{invariant.detail}</p>
              </div>
            </li>
          ))}
        </ol>
      </Card>

      <Card className="mb-5">
        <CardHeader title="Layers" subtitle="Where each kind of code lives" />
        <table className="w-full text-[13px]">
          <tbody>
            {architecture.layers.map((layer) => (
              <tr key={layer.path} className="border-b border-rule-soft last:border-0">
                <td className="px-5 py-2.5 font-mono text-[12px] whitespace-nowrap">
                  {layer.path}
                </td>
                <td className="py-2.5 pr-5 text-ink-muted">{layer.purpose}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader
            title="Backend dependencies"
            subtitle={`Python ${architecture.python} · from pyproject.toml`}
          />
          <table className="w-full text-[13px]">
            <tbody>
              {architecture.backend_dependencies.map((dependency) => (
                <tr key={dependency.name} className="border-b border-rule-soft last:border-0">
                  <td className="px-5 py-2 font-mono text-[12px]">{dependency.name}</td>
                  <td className="py-2 pr-5 text-right font-mono text-[12px] text-ink-muted">
                    {dependency.version || "—"}
                    {"extra" in dependency && dependency.extra ? (
                      <span className="ml-2 text-[11px]">[{String(dependency.extra)}]</span>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>

        <Card>
          <CardHeader title="Frontend dependencies" subtitle="from package.json" />
          <table className="w-full text-[13px]">
            <tbody>
              {architecture.frontend_dependencies.map((dependency) => (
                <tr key={dependency.name} className="border-b border-rule-soft last:border-0">
                  <td className="px-5 py-2 font-mono text-[12px]">{dependency.name}</td>
                  <td className="py-2 pr-5 text-right font-mono text-[12px] text-ink-muted">
                    {dependency.version}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>
    </>
  );
}
