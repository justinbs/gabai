import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { Button, FOCUS_LINK } from "../components/ui";
import { usePageTitle } from "../lib/usePageTitle";
import { useSession } from "../session-context";

const FIELD =
  "mt-2 block w-full border-2 border-ink px-3 py-2 text-[19px] focus:outline-3 focus:outline-ink focus-visible:shadow-[0_0_0_4px_#ffdd00]";

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
  <div className="min-h-screen bg-white px-4 py-12">
    <main className="mx-auto max-w-md">
      <div className="flex flex-col items-center text-center">
        <img
          src="/barangay-logo.jpg"
          alt="Barangay V logo"
          className="h-40 w-40 object-contain"
        />
        <h1 className="mt-3 text-[24px] font-bold tracking-tight">GABAI</h1>
        <p className="mt-1 text-[19px] text-muted">
          Barangay V (Singko), Amaya, Tanza, Cavite
        </p>
      </div>

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

          <label htmlFor="email" className="block text-[19px] font-bold">
            Email
          </label>
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={FIELD}
          />

          <label htmlFor="password" className="mt-5 block text-[19px] font-bold">
            Password
          </label>
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={FIELD}
          />

          <Button type="submit" disabled={busy} className="mt-6">
            {busy ? "Signing in" : "Sign in"}
          </Button>
        </form>

        <p className="mt-6">
          <Link to="/register" className={`text-link underline ${FOCUS_LINK}`}>
            Create an account
          </Link>
        </p>
      </main>
    </div>
  );
}