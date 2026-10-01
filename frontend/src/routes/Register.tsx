import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import * as api from "../api/client";
import { ApiError } from "../api/http";
import { PublicShell } from "../components/SiteChrome";
import { Button, FOCUS_LINK, Input } from "../components/ui";
import { bilingualPolicy } from "../lib/passwordMessages";
import { usePageTitle } from "../lib/usePageTitle";
import { useSession } from "../session-context";
import { TERMS_VERSION } from "../content/terms";


export function Register() {
  usePageTitle("Create an account");
  const { signIn } = useSession();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [residence, setResidence] = useState("");
  const [agreed, setAgreed] = useState(false);
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
    if (!agreed) {
      setError(
        "Agree to the terms and privacy notice to sign up · Sumang-ayon po sa mga tuntunin para makapag-sign up",
      );
      return;
    }
    setError("");
    setBusy(true);
    try {
      const created = await api.register({
        full_name: name,
        email,
        password,
        residence,
        terms_version: TERMS_VERSION,
      });
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
          : err instanceof ApiError && err.status === 409
            ? "The terms changed while this page was open. Reload the page · Nagbago ang mga tuntunin, i-reload po ang page"
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

          <div className="mt-6 flex items-start gap-3">
            <input
              id="agree"
              type="checkbox"
              checked={agreed}
              onChange={(e) => setAgreed(e.target.checked)}
              className="mt-1 h-7 w-7 shrink-0 accent-brand"
            />
            <label htmlFor="agree" className="text-[17px]">
              I've read and agree to the{" "}
              <a href="/terms" target="_blank" rel="noopener" className={`text-link underline ${FOCUS_LINK}`}>
                Terms of Use
              </a>{" "}
              and{" "}
              <a href="/privacy" target="_blank" rel="noopener" className={`text-link underline ${FOCUS_LINK}`}>
                Privacy Notice
              </a>
              <span className="block text-muted">
                Nabasa ko at sang-ayon ako sa mga Tuntunin at Abiso sa Pagkapribado
              </span>
            </label>
          </div>

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