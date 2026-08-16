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
 * Documentation, development only.
 *
 * `import.meta.env.DEV` is replaced with a literal at build time, so in a production build this is
 * `false ? ... : null`. Rollup then drops the branch, the dynamic import goes with it, and the docs
 * chunk is never emitted — the code does not ship rather than merely being unreachable.
 */
const DocsRoutes = import.meta.env.DEV
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
