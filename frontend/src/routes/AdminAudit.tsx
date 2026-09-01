import { useState } from "react";

import * as api from "../api/client";
import {
  EmptyState,
  ErrorState,
  Loading,
  PageHeading,
  Select,
} from "../components/ui";
import { fullDate } from "../lib/format";
import { AUDIT_ACTION_LABELS } from "../api/types";
import type { AuditLogEntry } from "../api/types";
import { useAsync } from "../lib/useAsync";
import { usePageTitle } from "../lib/usePageTitle";

// A raw id is what makes a row point at one exact thing, so it stays in the
// title. The column shows something a person can read.
const handle = (row: AuditLogEntry) => {
  if (!row.object_id) return row.object_type.replace("_", " ");
  if (row.object_type === "request") return `Request ${row.object_id}`;
  if (row.object_type === "user") {
    const person = api.findPerson(row.object_id);
    return person ? person.full_name : "Account";
  }
  return `${row.object_type} ${row.object_id}`;
};

// `detail` is JSONB, so a value can be an object. Stringify rather than let it
// render as [object Object].
const format = (value: unknown) =>
  typeof value === "object" && value !== null ? JSON.stringify(value) : String(value);

// Read only. Nothing in the app edits or deletes a row, because a trail that can
// be changed is not a trail.
export function AdminAudit() {
  usePageTitle("Audit log");
  const [action, setAction] = useState("");
  const { state, reload } = useAsync(
    () => api.listAuditLog({ action: action || undefined }),
    [action],
  );

  return (
    <>
      <PageHeading title="Audit log" />

      <div className="mb-5 max-w-xs">
        <Select
          name="action"
          label="Action"
          value={action}
          onChange={(e) => setAction(e.target.value)}
        >
          <option value="">All</option>
          {api.auditActions.map((a) => (
            <option key={a} value={a}>
              {AUDIT_ACTION_LABELS[a] ?? a}
            </option>
          ))}
        </Select>
      </div>

      {state.status === "loading" && <Loading />}
      {state.status === "error" && (
        <ErrorState description={state.message} onRetry={reload} />
      )}
      {state.status === "ready" && state.data.length === 0 && (
        <EmptyState title="Nothing logged" description="No actions match" />
      )}
      {state.status === "ready" && state.data.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left">
            <caption className="sr-only">Audit log</caption>
            <thead>
              <tr className="border-b-2 border-ink">
                <th scope="col" className="whitespace-nowrap py-2 pr-4 font-bold">When</th>
                <th scope="col" className="py-2 pr-4 font-bold">Who</th>
                <th scope="col" className="py-2 pr-4 font-bold">Action</th>
                <th scope="col" className="py-2 pr-4 font-bold">On</th>
                <th scope="col" className="py-2 pr-4 font-bold">Detail</th>
                <th scope="col" className="whitespace-nowrap py-2 font-bold">From</th>
              </tr>
            </thead>
            <tbody>
              {state.data.map((row) => (
                <tr key={row.id} className="border-b border-rule">
                  <td className="whitespace-nowrap py-3 pr-4 align-top text-muted">
                    {fullDate(row.created_at)}
                  </td>
                  <td className="py-3 pr-4 align-top">
                    {/* Null actor means the system did it, auto-classification
                        and auto-routing both write rows with no human. */}
                    {row.actor ? row.actor.full_name : "System"}
                  </td>
                  <td className="py-3 pr-4 align-top">
                    {AUDIT_ACTION_LABELS[row.action] ?? row.action}
                  </td>
                  <td
                    className="py-3 pr-4 align-top text-muted"
                    title={row.object_id ?? undefined}
                  >
                    {handle(row)}
                  </td>
                  <td className="py-3 pr-4 align-top text-muted">
                    {row.detail
                      ? Object.entries(row.detail)
                          .map(([k, v]) => `${k}: ${format(v)}`)
                          .join(", ")
                      : ""}
                  </td>
                  <td className="whitespace-nowrap py-3 align-top text-muted">
                    {row.ip_address ?? ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
