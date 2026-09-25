import { useState } from "react";

import * as api from "../api/client";
import { ApiError } from "../api/http";
import type { User } from "../api/types";
import {
  Button,
  EmptyState,
  ErrorState,
  FOCUS_LINK,
  Loading,
  PageHeading,
} from "../components/ui";
import { fullDate } from "../lib/format";
import { useAsync } from "../lib/useAsync";
import { usePageTitle } from "../lib/usePageTitle";

type View = "pending" | "rejected";

export function SignUps() {
  usePageTitle("Sign-ups");
  const [view, setView] = useState<View>("pending");
  const { state, reload } = useAsync(() => api.listRegistrations(view), [view]);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState<string>();

  const decide = async (person: User, decision: "approved" | "rejected") => {
    if (
      decision === "rejected" &&
      !window.confirm(
        `Turn down ${person.full_name}? They can't use GABAI unless someone approves them later`,
      )
    ) {
      return;
    }
    setBusy(person.id);
    try {
      await api.decideRegistration(person.id, decision);
      setMessage(
        decision === "approved"
          ? `Approved ${person.full_name}`
          : `Turned down ${person.full_name}`,
      );
      reload();
    } catch (err) {
      setMessage(
        err instanceof ApiError && err.status === 409
          ? err.message
          : err instanceof ApiError && err.status === 404
            ? "That account's gone"
            : "Didn't save, try again",
      );
      reload();
    } finally {
      setBusy(undefined);
    }
  };

  const switchTo = (next: View) => {
    setMessage("");
    setView(next);
  };

  return (
    <>
      <PageHeading title="Sign-ups" />

      <div className="mb-5 flex gap-6">
        {(["pending", "rejected"] as const).map((v) => (
          <button
            key={v}
            type="button"
            aria-pressed={view === v}
            onClick={() => switchTo(v)}
            className={`${FOCUS_LINK} ${view === v ? "font-bold" : "text-link underline"}`}
          >
            {v === "pending" ? "Waiting" : "Turned down"}
          </button>
        ))}
      </div>

      <p
        role="status"
        aria-live="polite"
        className={message ? "mb-4 border-l-4 border-brand pl-3 font-bold" : "sr-only"}
      >
        {message}
      </p>

      {state.status === "loading" && <Loading />}
      {state.status === "error" && <ErrorState description={state.message} onRetry={reload} />}
      {state.status === "ready" &&
        (state.data.length === 0 ? (
          <EmptyState
            title={view === "pending" ? "No one waiting" : "No one turned down"}
            description={
              view === "pending" ? "New sign-ups show up here" : "Anyone turned down shows up here"
            }
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-left">
              <caption className="sr-only">
                {view === "pending" ? "Sign-ups waiting for approval" : "Turned down sign-ups"}
              </caption>
              <thead>
                <tr className="border-b-2 border-ink">
                  <th scope="col" className="py-2 pr-4 font-bold">Name</th>
                  <th scope="col" className="py-2 pr-4 font-bold">Email</th>
                  <th scope="col" className="py-2 pr-4 font-bold">Confirmed</th>
                  <th scope="col" className="py-2 pr-4 font-bold">Purok or street</th>
                  <th scope="col" className="whitespace-nowrap py-2 pr-4 font-bold">Signed up</th>
                  <th scope="col" className="py-2 font-bold">Decide</th>
                </tr>
              </thead>
              <tbody>
                {state.data.map((person) => (
                  <tr key={person.id} className="border-b border-rule">
                    <td className="py-3 pr-4 align-top">{person.full_name}</td>
                    <td className="py-3 pr-4 align-top text-muted">{person.email}</td>
                    <td className="py-3 pr-4 align-top">
                      {person.is_verified ? "Yes" : "Not yet"}
                    </td>
                    <td className="py-3 pr-4 align-top">{person.residence}</td>
                    <td className="whitespace-nowrap py-3 pr-4 align-top text-muted">
                      {fullDate(person.created_at)}
                    </td>
                    <td className="py-3 align-top">
                      <div className="flex flex-wrap gap-3">
                        <Button
                          disabled={busy === person.id}
                          aria-label={`Approve ${person.full_name}`}
                          onClick={() => decide(person, "approved")}
                        >
                          Approve
                        </Button>
                        {view === "pending" && (
                          <Button
                            variant="secondary"
                            disabled={busy === person.id}
                            aria-label={`Turn down ${person.full_name}`}
                            onClick={() => decide(person, "rejected")}
                          >
                            Turn down
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
    </>
  );
}
