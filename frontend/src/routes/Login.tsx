import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { PublicShell } from "../components/SiteChrome";
import { Button, FOCUS_LINK, Input } from "../components/ui";
import { usePageTitle } from "../lib/usePageTitle";
import { useSession } from "../session-context";

export function Login() {
  usePageTitle("Sign in");
  const { signIn } = useSession();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const ok = await signIn(email, password);
      if (!ok) {
        setError("Can't sign you in, check your email and password");
        return;
      }
      navigate("/");
    } catch {
      setError("Couldn't sign you in, try again");
    } finally {
      setBusy(false);
    }
  };

  return (
  <PublicShell>
    <div className="mx-auto max-w-md">
      {/* The seal and the barangay's name are in the masthead above */}
      <h1 className="text-[36px] font-bold tracking-tight">GABAI</h1>

        <form
          onSubmit={submit}
          noValidate
          className="mt-8 border-t-2 border-ink pt-6"
        >
          <p
            role="alert"
            className={
              error
                ? "mb-4 border-l-4 border-danger bg-white p-3 font-bold text-danger"
                : "sr-only"
            }
          >
            {error}
          </p>

          <Input
            id="email"
            name="email"
            label="Email"
            type="email"
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <Input
            id="password"
            name="password"
            label="Password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-5"
          />

          <Button type="submit" disabled={busy} className="mt-6">
            {busy ? "Signing in" : "Sign in"}
          </Button>
        </form>

        <p className="mt-4">
          <Link to="/forgot-password" className={`text-link underline ${FOCUS_LINK}`}>
            Forgot your password?
          </Link>
        </p>

        <p className="mt-6">
          <Link to="/register" className={`text-link underline ${FOCUS_LINK}`}>
            Create an account
          </Link>
        </p>
      </div>
    </PublicShell>
  );
}