import { useState } from "react";

import * as api from "../api/client";
import { EmptyState, ErrorState, Loading, PageHeading } from "../components/ui";
import { useAsync } from "../lib/useAsync";
import { usePageTitle } from "../lib/usePageTitle";
import type { RoutingRule, User } from "../api/types";

// Categories come from the API, never from a list in here. The taxonomy is not
// locked yet and this screen renders whatever it is given.
export function AdminRouting() {
  usePageTitle("Routing");
  const { state, reload } = useAsync(
    () => Promise.all([api.listRoutingRules(), api.listUsers()]),
    [],
  );
  const [message, setMessage] = useState("");

  return (
    <>
      <PageHeading title="Routing" description="Who gets which category" />

      <p
        role="status"
        aria-live="polite"
        className={message ? "mb-4 border-l-4 border-brand pl-3 font-bold" : "sr-only"}
      >
        {message}
      </p>

      {state.status === "loading" && <Loading />}
      {state.status === "error" && (
        <ErrorState description={state.message} onRetry={reload} />
      )}
      {state.status === "ready" && state.data[0].length === 0 && (
        <EmptyState
          title="No categories yet"
          description="Add categories before setting handlers"
        />
      )}
      {state.status === "ready" && state.data[0].length > 0 && (
        <Rules
          rules={state.data[0]}
          staff={state.data[1].filter((u) => u.role !== "citizen")}
          onSaved={(text) => {
            setMessage(text);
            reload();
          }}
        />
      )}
    </>
  );
}

function Rules({
  rules,
  staff,
  onSaved,
}: {
  rules: RoutingRule[];
  staff: User[];
  onSaved: (message: string) => void;
}) {
  const [busy, setBusy] = useState<number>();

  // One handler per category. Two would make routing depend on insertion order,
  // and the schema enforces the same thing with a partial unique index.
  const assign = async (
    categoryId: number,
    staffId: string,
    name: string,
    category: string,
  ) => {
    setBusy(categoryId);
    const ok = await api.setRoutingRule(categoryId, staffId);
    setBusy(undefined);
    onSaved(ok ? `${name} now handles ${category}` : "Didn't save, try again");
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-left">
        <caption className="sr-only">Category handlers</caption>
        <thead>
          <tr className="border-b-2 border-ink">
            <th scope="col" className="py-2 pr-4 font-bold">Category</th>
            <th scope="col" className="py-2 pr-4 font-bold">Covers</th>
            <th scope="col" className="py-2 font-bold">Handled by</th>
          </tr>
        </thead>
        <tbody>
          {rules.map((rule) => (
            <tr key={rule.id} className="border-b border-rule">
              <td className="py-3 pr-4 align-top font-bold">
                {rule.category.name}
              </td>
              <td className="py-3 pr-4 align-top text-muted">
                {rule.category.description}
              </td>
              <td className="py-3 align-top">
                <label className="sr-only" htmlFor={`rule-${rule.id}`}>
                  Handler for {rule.category.name}
                </label>
                <select
                  id={`rule-${rule.id}`}
                  value={rule.staff.id}
                  disabled={busy === rule.category.id}
                  onChange={(e) => {
                    const picked = staff.find((s) => s.id === e.target.value);
                    if (picked) {
                      assign(
                        rule.category.id,
                        picked.id,
                        picked.full_name,
                        rule.category.name,
                      );
                    }
                  }}
                  className="border-2 border-ink bg-white px-2 py-1 focus:outline-3 focus:outline-ink"
                >
                  {staff
                    .filter((s) => s.is_active || s.id === rule.staff.id)
                    .map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.full_name}
                        {s.is_active ? "" : " (deactivated)"}
                      </option>
                    ))}
                </select>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
