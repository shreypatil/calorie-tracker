/**
 * Shared UI primitives.
 *
 * The house style: rules rather than shadows, mono tabular numerals for every
 * value, and uppercase micro-labels — the discipline of a nutrition panel. No
 * motion anywhere.
 */

import { useRef } from "react";
import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from "react";

import { cx } from "../lib/cx";

export function Card({
  children,
  className,
  ...rest
}: { children: ReactNode; className?: string } & React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cx("rounded-md border border-rule bg-surface", className)}
      {...rest}
    >
      {children}
    </div>
  );
}

export function CardHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-3 border-b border-rule px-5 py-4">
      <div>
        <h2 className="text-[15px] font-semibold tracking-tight">{title}</h2>
        {subtitle && <p className="mt-0.5 text-[13px] text-ink-muted">{subtitle}</p>}
      </div>
      {actions}
    </div>
  );
}

const BUTTON_VARIANTS = {
  primary: "bg-accent text-white border-accent hover:bg-[#0b5b51]",
  secondary: "bg-surface text-ink border-rule hover:bg-paper",
  danger: "bg-surface text-danger border-rule hover:bg-danger-soft",
} as const;

export function Button({
  variant = "secondary",
  className,
  ...rest
}: { variant?: keyof typeof BUTTON_VARIANTS } & ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={cx(
        "inline-flex items-center justify-center gap-1.5 rounded border px-3 py-1.5",
        "text-[13px] font-medium disabled:cursor-not-allowed disabled:opacity-50",
        BUTTON_VARIANTS[variant],
        className,
      )}
      {...rest}
    />
  );
}

export function Field({
  label,
  error,
  hint,
  children,
  className,
}: {
  label: string;
  error?: string;
  hint?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <label className={cx("block", className)}>
      <span className="eyebrow block pb-1.5">{label}</span>
      {children}
      {error ? (
        <span className="mt-1 block text-[12px] text-danger">{error}</span>
      ) : hint ? (
        <span className="mt-1 block text-[12px] text-ink-muted">{hint}</span>
      ) : null}
    </label>
  );
}

const CONTROL =
  "w-full rounded border border-rule bg-surface px-2.5 py-1.5 text-[14px] " +
  "placeholder:text-ink-muted focus:border-accent";

export function Input({ className, ...rest }: InputHTMLAttributes<HTMLInputElement>) {
  // Numeric inputs get mono figures so they line up with the values they become.
  const numeric = rest.type === "number" || rest.inputMode === "decimal";
  return (
    <input className={cx(CONTROL, numeric && "font-mono tabular", className)} {...rest} />
  );
}

export function Select({ className, ...rest }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={cx(CONTROL, className)} {...rest} />;
}

/**
 * A file control that reads as one button plus a filename.
 *
 * The native `<input type="file">` renders its button and its "no file selected" text as a single
 * fused control that cannot be styled and does not look like anything else in the app. The fix is
 * the standard one: hide the input, drive it from a real Button, and show the chosen name as
 * separate adjacent text. The input keeps its own accessible name so it is still reachable.
 */
export function FilePicker({
  accept,
  label,
  onSelect,
  disabled,
  filename,
  buttonText = "Choose a file",
}: {
  accept: string;
  label: string;
  onSelect: (file: File) => void;
  disabled?: boolean;
  filename?: string | null;
  buttonText?: string;
}) {
  const ref = useRef<HTMLInputElement>(null);

  return (
    <div className="flex flex-wrap items-center gap-3">
      <Button type="button" disabled={disabled} onClick={() => ref.current?.click()}>
        {buttonText}
      </Button>
      <span className={cx("text-[13px]", filename ? "text-ink-soft" : "text-ink-muted")}>
        {filename ?? "No file chosen"}
      </span>
      <input
        ref={ref}
        type="file"
        accept={accept}
        aria-label={label}
        className="sr-only"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) onSelect(file);
          // Cleared so re-picking the same file still fires a change event.
          event.target.value = "";
        }}
      />
    </div>
  );
}

/** A number in the house style: mono, tabular, right-aligned by default. */
export function Value({
  children,
  className,
  unit,
}: {
  children: ReactNode;
  className?: string;
  unit?: string;
}) {
  return (
    <span className={cx("font-mono tabular", className)}>
      {children}
      {unit && <span className="ml-1 text-[0.8em] text-ink-muted">{unit}</span>}
    </span>
  );
}

export function Alert({
  children,
  tone = "danger",
}: {
  children: ReactNode;
  tone?: "danger" | "info";
}) {
  return (
    <div
      role="alert"
      className={cx(
        "rounded border px-3 py-2 text-[13px]",
        tone === "danger"
          ? "border-danger/30 bg-danger-soft text-danger"
          : "border-rule bg-paper text-ink-soft",
      )}
    >
      {children}
    </div>
  );
}

/** An empty screen is an invitation to act, so it always offers the next step. */
export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="px-5 py-12 text-center">
      <p className="text-[14px] font-medium">{title}</p>
      <p className="mx-auto mt-1 max-w-sm text-[13px] text-ink-muted">{description}</p>
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </div>
  );
}

export function Loading({ label = "Loading" }: { label?: string }) {
  return <p className="px-5 py-12 text-center text-[13px] text-ink-muted">{label}…</p>;
}

export function ErrorNote({ error }: { error: unknown }) {
  const message = error instanceof Error ? error.message : "Something went wrong.";
  return (
    <div className="px-5 py-8">
      <Alert>{message}</Alert>
    </div>
  );
}

/** A horizontal meter for "value against target". */
export function Meter({
  value,
  target,
  tone = "accent",
}: {
  value: number;
  target: number | null;
  tone?: "accent" | "protein" | "carbs" | "fat";
}) {
  if (!target) return <div className="h-1.5 rounded-full bg-rule-soft" />;

  const ratio = Math.min(value / target, 1);
  const over = value > target;
  const colors = {
    accent: "bg-accent",
    protein: "bg-protein",
    carbs: "bg-carbs",
    fat: "bg-fat",
  } as const;

  return (
    <div
      className="h-1.5 overflow-hidden rounded-full bg-rule-soft"
      role="meter"
      aria-valuenow={Math.round(value)}
      aria-valuemin={0}
      aria-valuemax={Math.round(target)}
    >
      <div
        className={cx("h-full rounded-full", over ? "bg-warn" : colors[tone])}
        style={{ width: `${Math.max(ratio * 100, value > 0 ? 2 : 0)}%` }}
      />
    </div>
  );
}
