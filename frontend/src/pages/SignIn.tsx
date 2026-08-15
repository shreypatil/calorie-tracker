import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { Alert, Button, Card, Field, Input } from "../components/ui";

export function SignIn() {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await signIn(email, password);
      navigate("/");
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 401
          ? "Email or password is incorrect."
          : "Could not sign in. Check your connection and try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  return <AuthShell
    title="Sign in"
    footer={
      <>
        No account yet? <Link className="text-accent underline" to="/register">Create one</Link>
      </>
    }
  >
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && <Alert>{error}</Alert>}
      <Field label="Email">
        <Input
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
      </Field>
      <Field label="Password">
        <Input
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </Field>
      <Button type="submit" variant="primary" className="w-full" disabled={busy}>
        {busy ? "Signing in…" : "Sign in"}
      </Button>
    </form>
  </AuthShell>;
}

export function AuthShell({
  title,
  children,
  footer,
}: {
  title: string;
  children: React.ReactNode;
  footer: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen items-center justify-center px-5 py-12">
      <div className="w-full max-w-sm">
        <div className="mb-6">
          <p className="eyebrow">Personal calorie tracker</p>
          <h1 className="mt-1 text-[26px] font-semibold tracking-tight">Nutrition Ledger</h1>
        </div>

        <Card className="p-5">
          <h2 className="mb-4 text-[15px] font-semibold">{title}</h2>
          {children}
        </Card>

        <p className="mt-4 text-center text-[13px] text-ink-muted">{footer}</p>
      </div>
    </div>
  );
}
