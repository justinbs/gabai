import * as api from "../api/client";
import { RequestTable } from "../components/RequestTable";
import { EmptyState, ErrorState, Help, Loading, PageHeading } from "../components/ui";
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
      <Help>
        <p>These are the requests assigned to you and those in the categories you handle, highest urgency first and oldest first within each level.</p>
        <p>Open a request to move it along: in progress, then resolved, then closed. A note you add is sent to the resident.</p>
        <p>If the category or urgency is wrong, correct it on the request. It moves to the person who handles the new category.</p>
      </Help>

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
