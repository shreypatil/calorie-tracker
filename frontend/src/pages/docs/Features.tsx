/**
 * What each feature does, how to use it, and what happens internally.
 *
 * Parsed from `docs/features.md`, and — the part that matters — verified against the code at
 * generation time. Every endpoint named below exists in the API's OpenAPI spec and every file path
 * exists on disk, because `make docs` fails otherwise. A guide that confidently references a route
 * deleted six months ago is the normal failure mode for documentation like this.
 */

import { Card, CardHeader } from "../../components/ui";
import features from "../../docs/generated/features.json";

function Detail({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-1 sm:grid-cols-[7rem_1fr] sm:gap-4">
      <p className="eyebrow sm:pt-0.5">{label}</p>
      <div className="text-[13px] text-ink-soft">{children}</div>
    </div>
  );
}

export function Features() {
  return (
    <>
      <p className="mb-5 text-[13px] text-ink-muted">
        One section per feature. Every endpoint and file path shown here was verified to exist when
        these pages were generated — a stale reference fails <span className="font-mono">make docs</span>{" "}
        rather than being published.
      </p>

      {features.features.map((feature) => (
        <Card key={feature.name} className="mb-5">
          <CardHeader title={feature.name} subtitle={feature.screen} />

          <div className="space-y-4 px-5 py-4">
            <p className="text-[14px]">{feature.summary}</p>

            <Detail label="How to use">{feature.use}</Detail>
            <Detail label="Internally">{feature.internal}</Detail>

            {feature.safeguard && (
              <Detail label="Safeguard">
                <span className="text-ink">{feature.safeguard}</span>
              </Detail>
            )}

            {feature.control.length > 0 && (
              <Detail label="Controls">
                <ul className="space-y-1">
                  {feature.control.map((control) => {
                    const [name, ...rest] = control.split(" — ");
                    return (
                      <li key={control}>
                        <span className="font-medium text-ink">{name}</span>
                        {rest.length > 0 && <span> — {rest.join(" — ")}</span>}
                      </li>
                    );
                  })}
                </ul>
              </Detail>
            )}

            {feature.endpoint.length > 0 && (
              <Detail label="Endpoints">
                <ul className="space-y-0.5 font-mono text-[12px]">
                  {feature.endpoint.map((endpoint) => (
                    <li key={endpoint}>{endpoint}</li>
                  ))}
                </ul>
              </Detail>
            )}

            {feature.source.length > 0 && (
              <Detail label="Source">
                <ul className="space-y-0.5 font-mono text-[12px]">
                  {feature.source.map((source) => (
                    <li key={source}>{source}</li>
                  ))}
                </ul>
              </Detail>
            )}
          </div>
        </Card>
      ))}
    </>
  );
}
