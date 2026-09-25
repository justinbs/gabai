import { useState } from "react";
import { useNavigate } from "react-router-dom";

import * as api from "../api/client";
import { ApiError } from "../api/http";
import { ROLE_LABELS } from "../api/types";
import { Button, Input, PageHeading } from "../components/ui";
import { usePageTitle } from "../lib/usePageTitle";
import { useSession, useUser } from "../session-context";

export function Account() {
  usePageTitle("Your account");
  const user = useUser();
  const { refresh } = useSession();
  const navigate = useNavigate();
  // Set when an admin made the account or reset it. The server refuses
  // everything else until it's cleared, this screen just says why.
  const temporary = user.must_change_password;

  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [linkSent, setLinkSent] = useState(false);

  const sendConfirmation = async () => {
    setLinkSent(false);
    try {
      await api.requestVerifyEmail(user.email);
      setLinkSent(true);
    } catch {
      setError("Didn't send, try again");
    }
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!current || !next) {
      setError("Fill in both passwords");
      return;
    }
    setError("");
    setSaved(false);
    setBusy(true);
    try {
      await api.changePassword(current, next);
      setCurrent("");
      setNext("");
      if (temporary) {
        await refresh();
        navigate("/");
        return;
      }
      setSaved(true);
    } catch (err) {
      setError(
        err instanceof ApiError && (err.status === 400 || err.status === 422)
          ? err.message
          : "Didn't save, try again",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <PageHeading title="Your account" />

      {temporary && (
        <p className="mb-6 border-l-4 border-brand pl-3 text-[19px] font-bold">
          You're on a temporary password, pick your own to keep going
        </p>
      )}

      <dl className="grid max-w-md grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-[19px]">
        <dt className="text-muted">Name</dt>
        <dd>{user.full_name}</dd>
        <dt className="text-muted">Email</dt>
        <dd className="break-all">
          {user.email}
          <span className="text-muted">{user.is_verified ? ", confirmed" : ", not confirmed"}</span>
        </dd>
        <dt className="text-muted">Role</dt>
        <dd>{ROLE_LABELS[user.role]}</dd>
      </dl>

      {!user.is_verified && (
        <div className="mt-6 max-w-md">
          <p>Confirm it so you can reset your password by email</p>
          <p
            role="status"
            aria-live="polite"
            className={linkSent ? "mt-2 font-bold" : "sr-only"}
          >
            {linkSent ? "Link sent, check spam too" : ""}
          </p>
          <Button variant="secondary" className="mt-3" onClick={sendConfirmation}>
            Send confirmation link
          </Button>
        </div>
      )}

      <form onSubmit={submit} noValidate className="mt-10 max-w-md border-t-2 border-ink pt-5">
        <h2 className="text-[24px] font-bold">Change password</h2>

        <p
          role="status"
          aria-live="polite"
          className={saved ? "mt-3 border-l-4 border-brand pl-3 font-bold" : "sr-only"}
        >
          {saved ? "Password changed" : ""}
        </p>
        <p
          role="alert"
          className={
            error
              ? "mt-3 border-l-4 border-danger bg-white p-3 font-bold text-danger"
              : "sr-only"
          }
        >
          {error}
        </p>

        <Input
          id="current-password"
          label={temporary ? "Temporary password" : "Current password"}
          type="password"
          autoComplete="current-password"
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
          className="mt-4"
        />
        <Input
          id="new-password"
          label="New password"
          hint="At least 8 characters"
          type="password"
          autoComplete="new-password"
          value={next}
          onChange={(e) => setNext(e.target.value)}
          className="mt-5"
        />

        <Button type="submit" disabled={busy} className="mt-6">
          {busy ? "Saving" : "Change password"}
        </Button>
      </form>
    </>
  );
}
