/** The signed-in shell: identity, navigation, and the page body. */

import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { Button } from "./ui";
import { cx } from "../lib/cx";
import { DOCS_ENABLED } from "../lib/docs";

const NAV = [
  { to: "/", label: "Today", end: true },
  { to: "/entries", label: "Entries" },
  { to: "/reports", label: "Reports" },
  { to: "/goals", label: "Goals" },
  { to: "/import", label: "Import" },
  { to: "/chat", label: "Assistant" },
  // Development, or a build compiled with VITE_SHOW_DOCS=true. The flag is a literal at build
  // time, so when it is off this entry — and the docs bundle behind it — is absent entirely.
  ...(DOCS_ENABLED ? [{ to: "/docs", label: "Docs" }] : []),
];

export function Layout() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();

  return (
    <div className="min-h-screen">
      <header className="border-b border-rule bg-surface">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-8 gap-y-3 px-5 py-3">
          <div className="flex items-baseline gap-2">
            <span className="text-[15px] font-semibold tracking-tight">Nutrition Ledger</span>
          </div>

          <nav className="-mb-3 flex gap-1 order-3 w-full sm:order-none sm:w-auto sm:mb-0">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  cx(
                    "border-b-2 px-3 py-2 text-[13px] sm:py-1.5",
                    isActive
                      ? "border-accent font-medium text-ink"
                      : "border-transparent text-ink-muted hover:text-ink",
                  )
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-3">
            <span className="hidden text-[13px] text-ink-muted sm:inline">
              {user?.display_name}
            </span>
            <Button
              onClick={async () => {
                await signOut();
                navigate("/login");
              }}
            >
              Sign out
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-5 py-8">
        <Outlet />
      </main>
    </div>
  );
}

export function PageHeading({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-[22px] font-semibold tracking-tight">{title}</h1>
        {description && <p className="mt-1 text-[13px] text-ink-muted">{description}</p>}
      </div>
      {actions && <div className="flex gap-2">{actions}</div>}
    </div>
  );
}
