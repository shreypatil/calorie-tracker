/** Functional and non-functional requirements, parsed from `requirements.md`. */

import { InlineMarkdown } from "../../components/InlineMarkdown";
import { Card, CardHeader, Value } from "../../components/ui";
import requirements from "../../docs/generated/requirements.json";

type Requirement = (typeof requirements.items)[number];

function Group({ title, subtitle, items }: { title: string; subtitle: string; items: Requirement[] }) {
  return (
    <Card className="mb-5">
      <CardHeader title={title} subtitle={subtitle} />
      <table className="w-full text-[13px]">
        <thead>
          <tr className="border-b border-rule">
            <th className="eyebrow px-5 py-2 text-left font-normal">ID</th>
            <th className="eyebrow px-5 py-2 text-left font-normal">Requirement</th>
            <th className="eyebrow px-5 py-2 text-right font-normal">Criteria</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id} className="border-b border-rule-soft align-top last:border-0">
              <td className="px-5 py-3 whitespace-nowrap">
                <span className="font-mono text-[12px] font-medium">{item.id}</span>
              </td>
              <td className="px-5 py-3">
                <p className="font-medium">{item.title}</p>
                <p className="mt-1 text-ink-muted">
                  <InlineMarkdown text={item.description} />
                </p>
                {item.criteria.length > 0 && (
                  <ul className="mt-2 space-y-1">
                    {item.criteria.map((criterion) => (
                      <li key={criterion} className="flex gap-2 text-ink-soft">
                        <span aria-hidden className="text-accent">
                          ✓
                        </span>
                        <span>
                          <InlineMarkdown text={criterion} />
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </td>
              <td className="px-5 py-3 text-right">
                <Value>{item.criteria.length || "—"}</Value>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

export function Requirements() {
  const functional = requirements.items.filter((item) => item.kind === "functional");
  const nonFunctional = requirements.items.filter((item) => item.kind === "non-functional");

  return (
    <>
      <Group
        title="Functional requirements"
        subtitle={`${functional.length} requirements, all implemented`}
        items={functional}
      />
      <Group
        title="Non-functional requirements"
        subtitle={`${nonFunctional.length} requirements`}
        items={nonFunctional}
      />
    </>
  );
}
