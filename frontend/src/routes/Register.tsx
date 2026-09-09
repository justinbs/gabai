import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import * as api from "../api/client";
import { Button, FOCUS_LINK } from "../components/ui";
import { usePageTitle } from "../lib/usePageTitle";
import { useSession } from "../session-context";

const FIELD =
  "mt-2 block w-full border-2 border-ink px-3 py-2 text-[19px] focus:outline-3 focus:outline-ink focus-visible:shadow-[0_0_0_4px_#ffdd00]";

export function Register() {
  usePageTitle("Create an account");
  const { signIn } = useSession();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!name.trim()) {
      setError("We need your name · Kailangan po ang pangalan ninyo");
      return;
    }
    if (!email.trim()) {
      setError("We need your email · Kailangan po ang email ninyo");
      return;
    }
    if (password.length < 8) {
      setError("Password needs 8 characters · Kailangan ng 8 karakter");
      return;
    }
    setError("");
    setBusy(true);
    try {
      const created = await api.register({ full_name: name, email, password });
      if (!created) {
        setError("Someone already uses that email · May gumagamit na nito");
        return;
      }
      const ok = await signIn(created.email, password);
      if (!ok) {
        setError("Account made, please sign in · Nagawa na, mag-sign in po");
        return;
      }
      navigate("/requests");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen bg-white px-4 py-12">
      <main className="mx-auto max-w-md">
        <h1 className="text-[36px] font-bold tracking-tight">Create an account</h1>
        <p className="mt-1 text-[19px] text-muted">Gumawa ng account</p>

        <form onSubmit={submit} noValidate className="mt-8 border-t-2 border-ink pt-6">
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

          <label htmlFor="name" className="block text-[19px] font-bold">
            Full name · Buong pangalan
          </label>
          <input id="name" value={name} onChange={(e) => setName(e.target.value)} className={FIELD} />

          <label htmlFor="email" className="mt-5 block text-[19px] font-bold">
            Email
          </label>
          <input
            id="email"
            type="email"
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={FIELD}
          />

          <label htmlFor="password" className="mt-5 block text-[19px] font-bold">
            Password
          </label>
          <p id="password-hint" className="mt-1 text-muted">
            At least 8 characters · Hindi bababa sa 8 karakter
          </p>
          <input
            id="password"
            type="password"
            autoComplete="new-password"
            aria-describedby="password-hint"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={FIELD}
          />

          <div className="mt-6 flex flex-wrap items-center gap-4">
            <Button type="submit" disabled={busy}>
              {busy ? "Creating" : "Create account · Gumawa"}
            </Button>
            <Link to="/" className={`text-link underline ${FOCUS_LINK}`}>
              I already have one · Meron na ako
            </Link>
          </div>
        </form>
      </main>
    </div>
  );
}