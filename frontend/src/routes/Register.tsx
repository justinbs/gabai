import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import * as api from "../api/client";
import { ApiError } from "../api/http";
import { PublicShell } from "../components/SiteChrome";
import { Button, FOCUS_LINK, Input } from "../components/ui";
import { bilingualPolicy } from "../lib/passwordMessages";
import { usePageTitle } from "../lib/usePageTitle";
import { useSession } from "../session-context";


export function Register() {
  usePageTitle("Create an account");
  const { signIn } = useSession();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [residence, setResidence] = useState("");
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
    if (!residence.trim()) {
      setError("We need your purok or street · Kailangan po ang purok o kalye ninyo");
      return;
    }
    if (!password) {
      setError("We need a password · Kailangan po ng password");
      return;
    }
    setError("");
    setBusy(true);
    try {
      const created = await api.register({ full_name: name, email, password, residence });
      if (!created) {
        setError("Someone already uses that email · May gumagamit na nito");
        return;
      }
      const ok = await signIn(created.email, password);
      if (!ok) {
        setError("Account made, please sign in · Nagawa na, mag-sign in po");
        return;
      }
      navigate("/");
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 422
          ? bilingualPolicy(err.message)
          : "Didn't save, try again · Hindi nai-save, subukan ulit",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <PublicShell>
      <div className="mx-auto max-w-md">
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

          <Input
            id="name"
            label="Full name · Buong pangalan"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <Input
            id="email"
            label="Email"
            type="email"
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-5"
          />
          <Input
            id="residence"
            label="Purok or street · Purok o kalye"
            hint="So the barangay can check you live here · Para matiyak ng barangay na taga-rito kayo"
            autoComplete="address-line1"
            value={residence}
            onChange={(e) => setResidence(e.target.value)}
            className="mt-5"
          />
          <Input
            id="password"
            label="Password"
            hint="At least 8 characters · Hindi bababa sa 8 karakter"
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-5"
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
      </div>
    </PublicShell>
  );
}