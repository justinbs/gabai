import * as api from "../api/client";
import { RequestTable } from "../components/RequestTable";
import { EmptyState, ErrorState, Loading, PageHeading } from "../components/ui";
import { useAsync } from "../lib/useAsync";
import { usePageTitle } from "../lib/usePageTitle";
import { useUser } from "../session-context";

// Highest urgency first, then oldest. That is the order the queue is worked.
// Sorting, not a separate pipeline: urgency changes position, never routing.
export function StaffQueue() {
  usePageTitle("Queue");
  const user = useUser();
  const { state, reload } = useAsync(
    () =>
      api.listRequests(user, {
        status: ["routed", "in_progress", "classified"],
      }),
    [user.id],
  );

  return (
    <>
      <PageHeading title="Queue" />

      {state.status === "loading" && <Loading label="Loading" />}

      {state.status === "error" && (
        <ErrorState description={state.message} onRetry={reload} />
      )}

      {state.status === "ready" &&
        (state.data.items.length === 0 ? (
          <EmptyState
            title="Queue is empty"
            description="Nothing assigned to you right now"
          />
        ) : (
          <RequestTable items={state.data.items} caption="Open requests" />
        ))}
    </>
  );
}
