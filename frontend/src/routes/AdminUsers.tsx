import { useEffect, useRef, useState } from "react";

import * as api from "../api/client";
import { ApiError } from "../api/http";
import {
  Button,
  EmptyState,
  ErrorState,
  Input,
  Loading,
  PageHeading,
  Select,
} from "../components/ui";
import { fullDate } from "../lib/format";
import { useAsync } from "../lib/useAsync";
import { usePageTitle } from "../lib/usePageTitle";
import { useUser } from "../session-context";
import { ROLE_LABELS } from "../api/types";
import type { Role, User } from "../api/types";

const ROLES: Role[] = ["citizen", "staff", "admin"];

export function AdminUsers() {
  usePageTitle("Accounts");
  const { state, reload } = useAsync(() => api.listUsers(), []);
  const [message, setMessage] = useState("");
  const [refusal, setRefusal] = useState("");
  // Shown once. Leaving the page loses it, and that's the point.
  const [issued, setIssued] = useState<{ name: string; password: string } | null>(null);
  const issuedRef = useRef<HTMLDivElement>(null);

  // The reset button can be far down the table. Focus scrolls the password into
  // view and gets a screen reader to read it, which a live region that mounts
  // with its text already in it often doesn't.
  useEffect(() => {
    if (issued) issuedRef.current?.focus();
  }, [issued]);

  const report = (text: string, ok: boolean) => {
    setMessage(ok ? text : "");
    setRefusal(ok ? "" : text);
    if (ok) reload();
  };

  return (
    <>
      <PageHeading title="Accounts" />

      {issued && (
        <div
          ref={issuedRef}
          tabIndex={-1}
          className="mb-6 border-l-4 border-brand pl-4 focus:outline-3 focus:outline-ink"
        >
          <p className="font-bold">Temporary password for {issued.name}</p>
          <p className="mt-1 select-all font-mono text-[28px] tracking-wider">
            {issued.password}
          </p>
          <p className="mt-1 text-muted">
            Read it to them, they'll pick their own when they sign in
          </p>
          <Button variant="secondary" className="mt-3" onClick={() => setIssued(null)}>
            Done
          </Button>
        </div>
      )}

      <p
        role="status"
        aria-live="polite"
        className={message ? "mb-4 border-l-4 border-brand pl-3 font-bold" : "sr-only"}
      >
        {message}
      </p>
      <p
        role="alert"
        className={
          refusal
            ? "mb-4 border-l-4 border-danger bg-white p-3 font-bold text-danger"
            : "sr-only"
        }
      >
        {refusal}
      </p>

      {state.status === "loading" && <Loading />}
      {state.status === "error" && (
        <ErrorState description={state.message} onRetry={reload} />
      )}
      {state.status === "ready" && (
        <>
          {state.data.length === 0 ? (
            <EmptyState title="No accounts" description="Add someone below" />
          ) : (
            <UserTable
              users={state.data}
              onChanged={report}
              onReset={(name, password) => {
                setMessage("");
                setRefusal("");
                setIssued({ name, password });
              }}
            />
          )}
          <NewUser onCreated={(text) => report(text, true)} />
        </>
      )}
    </>
  );
}

function UserTable({
  users,
  onChanged,
  onReset,
}: {
  users: User[];
  onChanged: (message: string, ok: boolean) => void;
  onReset: (name: string, password: string) => void;
}) {
  const me = useUser();
  const [busy, setBusy] = useState<string>();

  const reset = async (user: User) => {
    const sure = window.confirm(
      `Reset the password for ${user.full_name}? Their current one will stop working`,
    );
    if (!sure) return;
    setBusy(user.id);
    try {
      onReset(user.full_name, await api.resetPassword(user.id));
    } catch {
      onChanged("Didn't reset, try again", false);
    } finally {
      setBusy(undefined);
    }
  };

  // Client-side heuristic only, computed from the list we just fetched,
  // just so the button can warn before clicking. The server has final say
  // (409) regardless, using its own live count at the moment of the request.
  const activeAdminCount = users.filter((u) => u.role === "admin" && u.is_active).length;

  const change = async (
    user: User,
    patch: Partial<Pick<User, "role" | "is_active">>,
  ) => {
    setBusy(user.id);
    try {
      const updated = await api.updateUser(user.id, patch);
      onChanged(
        updated
          ? `Updated ${user.full_name}`
          : "That's the last admin, someone else needs the role first",
        Boolean(updated),
      );
    } catch {
      onChanged("Didn't save, try again", false);
    } finally {
      setBusy(undefined);
    }
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-left">
        <caption className="sr-only">Accounts</caption>
        <thead>
          <tr className="border-b-2 border-ink">
            <th scope="col" className="py-2 pr-4 font-bold">Name</th>
            <th scope="col" className="py-2 pr-4 font-bold">Email</th>
            <th scope="col" className="py-2 pr-4 font-bold">Role</th>
            <th scope="col" className="whitespace-nowrap py-2 pr-4 font-bold">Added</th>
            <th scope="col" className="py-2 pr-4 font-bold">Status</th>
            <th scope="col" className="py-2 font-bold">Change</th>
          </tr>
        </thead>
        <tbody>
          {users.map((user) => {
            const locked = user.role === "admin" && user.is_active && activeAdminCount === 1;
            return (
              <tr key={user.id} className="border-b border-rule">
                <td className="py-3 pr-4 align-top">{user.full_name}</td>
                <td className="py-3 pr-4 align-top text-muted">{user.email}</td>
                <td className="py-3 pr-4 align-top">
                  <label className="sr-only" htmlFor={`role-${user.id}`}>
                    Role for {user.full_name}
                  </label>
                  <select
                    id={`role-${user.id}`}
                    value={user.role}
                    disabled={busy === user.id || locked}
                    onChange={(e) => change(user, { role: e.target.value as Role })}
                    className="border-2 border-ink bg-white px-2 py-1 focus:outline-3 focus:outline-ink"
                  >
                    {ROLES.map((r) => (
                      <option key={r} value={r}>
                        {ROLE_LABELS[r]}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="whitespace-nowrap py-3 pr-4 align-top text-muted">
                  {fullDate(user.created_at)}
                </td>
                <td className="py-3 pr-4 align-top">
                  {!user.is_active
                    ? "Inactive"
                    : user.approval_status === "pending"
                      ? "Waiting for approval"
                      : user.approval_status === "rejected"
                        ? "Turned down"
                        : "Active"}
                </td>
                <td className="py-3 align-top">
                  <div className="flex flex-wrap gap-3">
                    {locked ? (
                      <span className="self-center text-muted">Last admin</span>
                    ) : (
                      <Button
                        variant="secondary"
                        disabled={busy === user.id}
                        aria-label={`${user.is_active ? "Deactivate" : "Reactivate"} ${user.full_name}`}
                        onClick={() => change(user, { is_active: !user.is_active })}
                      >
                        {user.is_active ? "Deactivate" : "Reactivate"}
                      </Button>
                    )}
                    {/* Your own is changed from Your account, where you know the old
                        one. An inactive account can't sign in, so a temporary
                        password for it would be useless */}
                    {user.id !== me.id && user.is_active && (
                      <Button
                        variant="secondary"
                        disabled={busy === user.id}
                        aria-label={`Reset password for ${user.full_name}`}
                        onClick={() => reset(user)}
                      >
                        Reset password
                      </Button>
                    )}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function NewUser({ onCreated }: { onCreated: (message: string) => void }) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<Role>("staff");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!name.trim() || !email.trim()) {
      setError("Name and email are both needed");
      return;
    }
    if (!password) {
      setError("Set a temporary password");
      return;
    }
    setError("");
    setBusy(true);
    try {
      const created = await api.createUser({ full_name: name, email, password, role });
      if (!created) {
        setError("Someone already uses that email");
        return;
      }
      setName("");
      setEmail("");
      setPassword("");
      onCreated(`Added ${created.full_name}, they'll pick their own password when they sign in`);
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 422 ? err.message : "Didn't save, try again",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} noValidate className="mt-10 border-t-2 border-ink pt-5">
      <h2 className="text-[24px] font-bold">Add someone</h2>

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

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <Input id="name" label="Name" value={name} onChange={(e) => setName(e.target.value)} />
        <Input
          id="new-email"
          label="Email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <Input
          id="new-password"
          label="Temporary password"
          type="password"
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <Select
          name="new-role"
          label="Role"
          value={role}
          onChange={(e) => setRole(e.target.value as Role)}
        >
          {ROLES.map((r) => (
            <option key={r} value={r}>
              {ROLE_LABELS[r]}
            </option>
          ))}
        </Select>
      </div>

      <Button type="submit" disabled={busy} className="mt-5">
        {busy ? "Adding" : "Add"}
      </Button>
    </form>
  );
}