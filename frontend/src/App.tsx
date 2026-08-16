import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { useAuth } from "./lib/auth";
import { Chat } from "./pages/Chat";
import { Dashboard } from "./pages/Dashboard";
import { Entries } from "./pages/Entries";
import { Goals } from "./pages/Goals";
import { Import } from "./pages/Import";
import { Reports } from "./pages/Reports";
import { SignIn } from "./pages/SignIn";
import { Register } from "./pages/Register";

/** Shown only while a stored token is being checked against the server. */
function SessionCheck() {
  return (
    <p className="px-5 py-16 text-center text-[13px] text-ink-muted">Signing you in…</p>
  );
}

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { status } = useAuth();

  // Wait for the stored token to be checked before deciding — otherwise a
  // reload bounces a signed-in user to the sign-in screen for a moment.
  if (status === "loading") return <SessionCheck />;
  if (status === "anonymous") return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function RedirectIfSignedIn({ children }: { children: React.ReactNode }) {
  const { status } = useAuth();
  if (status === "loading") return <SessionCheck />;
  if (status === "authenticated") return <Navigate to="/" replace />;
  return <>{children}</>;
}

/**
 * Documentation — on in development, and in any build compiled with `VITE_SHOW_DOCS=true`.
 *
 * `DOCS_ENABLED` folds to a literal at build time, so when it is false Rollup drops this branch,
 * the dynamic import goes with it, and the docs chunk is never emitted — the code does not ship
 * rather than merely being unreachable. The production bundle is grepped for docs strings in
 * verification, because that is the only real evidence.
 */
// Inlined rather than imported from `lib/docs.ts` on purpose. Rollup folds an `import.meta.env`
// literal in place, but would not fold the imported constant early enough to remove the `import()`
// below — which left a 62 KB docs chunk on disk even with the flag off. Verified by grepping the
// built bundle, not assumed.
const DocsRoutes = import.meta.env.DEV || import.meta.env.VITE_SHOW_DOCS === "true"
  ? lazy(async () => {
      const module = await import("./pages/docs");
      return { default: () => <Routes>{module.docsRoutes()}</Routes> };
    })
  : null;

export default function App() {
  return (
    <Routes>
      <Route
        path="/login"
        element={
          <RedirectIfSignedIn>
            <SignIn />
          </RedirectIfSignedIn>
        }
      />
      <Route
        path="/register"
        element={
          <RedirectIfSignedIn>
            <Register />
          </RedirectIfSignedIn>
        }
      />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="/entries" element={<Entries />} />
        <Route path="/reports" element={<Reports />} />
        <Route path="/goals" element={<Goals />} />
        <Route path="/import" element={<Import />} />
        <Route path="/chat" element={<Chat />} />
        {DocsRoutes && (
          <Route
            path="/docs/*"
            element={
              <Suspense fallback={null}>
                <DocsRoutes />
              </Suspense>
            }
          />
        )}
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
