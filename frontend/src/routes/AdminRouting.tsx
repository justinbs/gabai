import { useMemo, useState } from "react";

import * as api from "../api/client";
import { ApiError } from "../api/http";
import { EmptyState, ErrorState, Help, Loading, PageHeading } from "../components/ui";
import { useAsync } from "../lib/useAsync";
import { usePageTitle } from "../lib/usePageTitle";
import type { Category, RoutingRule, User } from "../api/types";

export function AdminRouting() {
  usePageTitle("Routing");
  const { state, reload } = useAsync(
    // Include switched-off categories so saving doesn't drop their handlers.
    () => Promise.all([api.listAllCategories(), api.listUsers(), api.listRoutingRules()]),
    [],
  );
  const [message, setMessage] = useState("");

  return (
    <>
      <PageHeading title="Routing" description="Who gets which category" />
      <Help>
        <p>Choose who handles each category. When the system is sure of a new request's category, it goes straight to that person.</p>
        <p>Each category has one handler. A change applies to new requests and to requests staff correct from now on.</p>
        <p>If a handler is deactivated or no longer staff, that category's new requests go to For review until you pick someone else.</p>
      </Help>

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
          categories={state.data[0]}
          users={state.data[1]}
          currentRules={state.data[2]}
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
  categories,
  users,
  currentRules,
  onSaved,
}: {
  categories: Category[];
  users: User[];
  currentRules: RoutingRule[];
  onSaved: (message: string) => void;
}) {
  // One dropdown value per category, seeded from whatever's currently active.
  // A category with no rule yet defaults to the first available staff member,
  // so every dropdown always shows a real selection matching what gets sent.
  const staff = useMemo(() => users.filter((u) => u.role !== "citizen" && u.is_active), [users]);
  const initial = useMemo(() => {
    const map = new Map<number, string>();
    for (const category of categories) {
      const existing = currentRules.find((r) => r.category.id === category.id && r.is_active);
      map.set(category.id, existing?.staff.id ?? staff[0]?.id ?? "");
    }
    return map;
  }, [categories, currentRules, staff]);

  const [selections, setSelections] = useState(initial);
  const [busy, setBusy] = useState(false);

  const assign = async (categoryId: number, staffId: string) => {
    const next = new Map(selections);
    next.set(categoryId, staffId);
    setSelections(next);

    setBusy(true);
    try {
      const rules = Array.from(next.entries())
        .filter(([, sid]) => sid)
        .map(([catId, sid]) => ({ categoryId: catId, staffId: sid }));
      const result = await api.replaceRoutingRules(rules);
      if (!result) {
        onSaved("Didn't save, try again");
        return;
      }
      const category = categories.find((c) => c.id === categoryId);
      const handler = users.find((s) => s.id === staffId);
      onSaved(
        category && handler
          ? `${handler.full_name} now handles ${category.name}`
          : "Saved",
      );
    } catch (err) {
      onSaved(err instanceof ApiError ? err.message : "Didn't save, try again");
    } finally {
      setBusy(false);
    }
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
          {categories.map((category) => {
            const selected = selections.get(category.id) ?? "";
            const current = users.find((u) => u.id === selected);
            const unusable = current !== undefined && !staff.includes(current);
            return (
              <tr key={category.id} className="border-b border-rule">
                <td className="py-3 pr-4 align-top font-bold">
                  {category.name}
                  {!category.is_active && <span className="block font-normal text-muted">Switched off</span>}
                </td>
                <td className="py-3 pr-4 align-top text-muted">{category.description}</td>
                <td className="py-3 align-top">
                  <label className="sr-only" htmlFor={`rule-${category.id}`}>
                    Handler for {category.name}
                  </label>
                  <select
                    id={`rule-${category.id}`}
                    value={selected}
                    disabled={busy}
                    onChange={(e) => assign(category.id, e.target.value)}
                    className="border-2 border-ink bg-white px-2 py-1 focus:outline-3 focus:outline-ink"
                  >
                    {unusable && (
                      <option value={current.id}>
                        {current.full_name} ({current.is_active ? "not staff" : "deactivated"})
                      </option>
                    )}
                    {staff.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.full_name}
                      </option>
                    ))}
                  </select>
                  {unusable && <span className="mt-1 block text-muted">New requests go to For review</span>}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}