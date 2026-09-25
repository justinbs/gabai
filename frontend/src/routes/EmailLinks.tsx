import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import * as api from "../api/client";
import { ApiError } from "../api/http";
import { PublicShell } from "../components/SiteChrome";
import { Button, FOCUS_LINK, Input } from "../components/ui";
import { bilingualPolicy, readTokenFromHash, useClearHash } from "../lib/passwordMessages";
import { usePageTitle } from "../lib/usePageTitle";
import { useSession } from "../session-context";

// The three pages an email link or the sign-in screen leads to. Residents use
// them, so they're bilingual like Register.

const LINK = `text-link underline ${FOCUS_LINK}`;
const ALERT = "mb-4 border-l-4 border-danger bg-white p-3 font-bold text-danger";
const DONE = "border-l-4 border-brand pl-3";

function Heading({ en, tl }: { en: string; tl: string }) {
  return (
    <>
      <h1 className="text-[36px] font-bold tracking-tight">{en}</h1>
      <p className="mt-1 text-[19px] text-muted">{tl}</p>
    </>
  );
}

export function ForgotPassword() {
  usePageTitle("Reset your password");
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!email.trim()) {
      setError("We need your email · Kailangan po ang email ninyo");
      return;
    }
    setError("");
    setBusy(true);
    try {
      await api.requestPasswordEmail(email);
      setSent(true);
    } catch {
      setError("Didn't send, try again · Hindi naipadala, subukan ulit");
    } finally {
      setBusy(false);
    }
  };

  return (
    <PublicShell>
      <div className="mx-auto max-w-md">
        <Heading en="Reset your password" tl="I-reset ang password" />

        {sent ? (
          <div role="status" className={`mt-8 ${DONE}`}>
            <p className="text-[19px] font-bold">
              If that email has a confirmed account, a link is on its way
            </p>
            <p className="mt-1 text-muted">Kung may account ito, may darating na link</p>
            <p className="mt-4">Check your spam folder too · Tingnan din ang spam</p>
          </div>
        ) : (
          <form onSubmit={submit} noValidate className="mt-8 border-t-2 border-ink pt-6">
            <p role="alert" className={error ? ALERT : "sr-only"}>
              {error}
            </p>
            <Input
              id="email"
              label="Email"
              type="email"
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <Button type="submit" disabled={busy} className="mt-6">
              {busy ? "Sending" : "Send link · Ipadala ang link"}
            </Button>
          </form>
        )}

        <p className="mt-8 text-muted">
          No email, or never confirmed it? The barangay office can reset it · Walang email?
          Ang barangay office ang magre-reset
        </p>
        <p className="mt-4">
          <Link to="/" className={LINK}>
            Back to sign in · Bumalik
          </Link>
        </p>
      </div>
    </PublicShell>
  );
}

export function ResetPassword() {
  usePageTitle("Set a new password");
  const [token] = useState(readTokenFromHash);
  useClearHash();
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [expired, setExpired] = useState(!token);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!password) {
      setError("We need a password · Kailangan po ng password");
      return;
    }
    setError("");
    setBusy(true);
    try {
      await api.setPasswordFromLink(token, password);
      setDone(true);
    } catch (err) {
      if (err instanceof ApiError && err.message === "RESET_PASSWORD_BAD_TOKEN") {
        setExpired(true);
      } else if (err instanceof ApiError && err.status === 400) {
        setError(bilingualPolicy(err.message));
      } else {
        setError("Didn't save, try again · Hindi nai-save, subukan ulit");
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <PublicShell>
      <div className="mx-auto max-w-md">
        <Heading en="Set a new password" tl="Magtakda ng bagong password" />

        {done ? (
          <div role="status" className={`mt-8 ${DONE}`}>
            <p className="text-[19px] font-bold">Password changed · Napalitan na ang password</p>
            <p className="mt-4">
              <Link to="/" className={LINK}>
                Sign in · Mag-sign in
              </Link>
            </p>
          </div>
        ) : expired ? (
          <div role="alert" className="mt-8 border-l-4 border-danger pl-3">
            <p className="text-[19px] font-bold">
              That link has expired or was already used
            </p>
            <p className="mt-1 text-muted">Luma na o nagamit na ang link</p>
            <p className="mt-4">
              <Link to="/forgot-password" className={LINK}>
                Get a new link · Humingi ng bago
              </Link>
            </p>
          </div>
        ) : (
          <form onSubmit={submit} noValidate className="mt-8 border-t-2 border-ink pt-6">
            <p role="alert" className={error ? ALERT : "sr-only"}>
              {error}
            </p>
            <Input
              id="new-password"
              label="New password · Bagong password"
              hint="At least 8 characters · Hindi bababa sa 8 karakter"
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <Button type="submit" disabled={busy} className="mt-6">
              {busy ? "Saving" : "Save password · I-save"}
            </Button>
          </form>
        )}
      </div>
    </PublicShell>
  );
}

export function VerifyEmail() {
  usePageTitle("Confirm your email");
  const { user, refresh } = useSession();
  const [token] = useState(readTokenFromHash);
  useClearHash();
  const [result, setResult] = useState<"checking" | "done" | "expired">(
    token ? "checking" : "expired",
  );
  // StrictMode runs effects twice in development. One request is enough.
  const started = useRef(false);

  useEffect(() => {
    if (!token || started.current) return;
    started.current = true;
    api
      .verifyEmail(token)
      .then(() => "done" as const)
      .catch((err) =>
        err instanceof ApiError && err.message === "VERIFY_USER_ALREADY_VERIFIED"
          ? ("done" as const)
          : ("expired" as const),
      )
      .then(async (outcome) => {
        // A signed-in resident's waiting page reads this, so update it
        if (outcome === "done") await refresh();
        setResult(outcome);
      });
  }, [token, refresh]);

  return (
    <PublicShell>
      <div className="mx-auto max-w-md">
        <Heading en="Confirm your email" tl="Kumpirmahin ang email" />

        {result === "checking" && (
          <p role="status" className="mt-8 text-[19px] text-muted">
            Checking the link
          </p>
        )}
        {result === "done" && (
          <div role="status" className={`mt-8 ${DONE}`}>
            <p className="text-[19px] font-bold">Email confirmed · Nakumpirma na ang email</p>
            <p className="mt-4">
              <Link to="/" className={LINK}>
                {user ? "Continue · Magpatuloy" : "Sign in · Mag-sign in"}
              </Link>
            </p>
          </div>
        )}
        {result === "expired" && (
          <div role="alert" className="mt-8 border-l-4 border-danger pl-3">
            <p className="text-[19px] font-bold">That link has expired</p>
            <p className="mt-1 text-muted">Luma na ang link</p>
            <p className="mt-4">
              Sign in to get a new one · Mag-sign in para makakuha ng bago
            </p>
            <p className="mt-4">
              <Link to="/" className={LINK}>
                Sign in · Mag-sign in
              </Link>
            </p>
          </div>
        )}
      </div>
    </PublicShell>
  );
}
