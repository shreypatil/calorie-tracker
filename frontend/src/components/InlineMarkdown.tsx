/**
 * Renders the small amount of inline markdown that survives into generated documentation.
 *
 * The docs are parsed out of markdown sources, so text arrives carrying `**bold**` and `` `code` ``
 * markers. Rendering it as plain text showed the asterisks and backticks literally. Stripping them
 * would have been easier but loses the emphasis the author put there deliberately — in
 * `requirements.md` the bold is almost always the load-bearing clause of a requirement.
 *
 * Deliberately not a markdown library and not `dangerouslySetInnerHTML`: only two inline forms are
 * needed, and building React elements means generated content can never inject markup.
 */

import type { ReactNode } from "react";

/** Capturing group, so `split` keeps the delimiters and their contents together. */
const INLINE = /(\*\*[^*]+\*\*|`[^`]+`)/g;

export function InlineMarkdown({ text }: { text: string }) {
  const parts = text.split(INLINE);

  return (
    <>
      {parts.map((part, index): ReactNode => {
        if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
          // Recursive, because the two forms nest: requirements.md contains
          // **versioned by `effective_from` date**, and rendering the bold content as plain text
          // left the backticks visible — which is the bug this component was written to fix.
          return (
            <strong key={index} className="font-medium text-ink">
              <InlineMarkdown text={part.slice(2, -2)} />
            </strong>
          );
        }
        if (part.startsWith("`") && part.endsWith("`") && part.length > 2) {
          return (
            <code key={index} className="rounded bg-rule-soft px-1 py-0.5 font-mono text-[0.92em]">
              {part.slice(1, -1)}
            </code>
          );
        }
        return part;
      })}
    </>
  );
}
