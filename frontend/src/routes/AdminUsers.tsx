import { useState } from "react";

import * as api from "../api/client";
import {
  Button,
  EmptyState,
  ErrorState,
  Loading,
  PageHeading,
  Select,
} from "../components/ui";
import { fullDate } from "../lib/format";
import { useAsync } from "../lib/useAsync";
import { usePageTitle } from "../lib/usePageTitle";
import { ROLE_LABELS } from "../api/types";
import type { Role, User } from "../api/types";

const ROLES: Role[] = ["citizen", "staff", "admin"];

const FIELD =
  "mt-2 block w-full border-2 border-ink px-3 py-2 text-[19px] focus:outline-3 focus:outline-ink focus-visible:shadow-[0_0_0_4px_#ffdd00]";

export function AdminUsers() {
  usePageTitle("Accounts");
  const { state, reload } = useAsync(() => api.listUsers(), []);
  const [message, setMessage] = useState("");
  const [refusal, setRefusal] = useState("");

  const report = (text: string, ok: boolean) => {
    // A blocked write is not a success. Green text in a polite live region is
    // the wrong channel for it.
    setMessage(ok ? text : "");
    setRefusal(ok ? "" : text);
    if (ok) reload();
  };

  return (
    <>
      <PageHeading title="Accounts" />

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
            <UserTable users={state.data} onChanged={report} />
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
}: {
  users: User[];
  onChanged: (message: string, ok: boolean) => void;
}) {
  const [busy, setBusy] = useState<string>();

  const change = async (
    user: User,
    patch: Partial<Pick<User, "role" | "is_active">>,
  ) => {
    setBusy(user.id);
    const updated = await api.updateUser(user.id, patch);
    setBusy(undefined);
    onChanged(
      updated
        ? `Updated ${user.full_name}`
        : "That's the last admin, someone else needs the role first",
      Boolean(updated),
    );
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
            const locked = api.isLastActiveAdmin(user);
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
                  {user.is_active ? "Active" : "Inactive"}
                </td>
                <td className="py-3 align-top">
                  {/* The last active admin cannot be demoted or deactivated, or
                      nobody can reach this screen again. */}
                  {locked ? (
                    <span className="text-muted">Last admin</span>
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
  const [role, setRole] = useState<Role>("staff");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!name.trim() || !email.trim()) {
      setError("Name and email are both needed");
      return;
    }
    setError("");
    setBusy(true);
    const created = await api.createUser({ full_name: name, email, role });
    setBusy(false);
    if (!created) {
      setError("Someone already uses that email");
      return;
    }
    setName("");
    setEmail("");
    onCreated(`Added ${created.full_name}`);
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

      <div className="mt-4 grid gap-4 sm:grid-cols-3">
        <div>
          <label htmlFor="name" className="block text-[19px] font-bold">
            Name
          </label>
          <input
            id="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className={FIELD}
          />
        </div>
        <div>
          <label htmlFor="new-email" className="block text-[19px] font-bold">
            Email
          </label>
          <input
            id="new-email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={FIELD}
          />
        </div>
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
