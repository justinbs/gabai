import * as api from "../api/client";
import { RequestTable } from "../components/RequestTable";
import { EmptyState, ErrorState, Loading, PageHeading } from "../components/ui";
import { useAsync } from "../lib/useAsync";
import { usePageTitle } from "../lib/usePageTitle";
import { useUser } from "../session-context";

// Oldest first, deliberately. This is a backlog, and the urgency shown here came
// from a prediction the system was not confident about, so sorting by it would be
// trusting the number the queue exists to doubt.
export function ReviewQueue() {
  usePageTitle("For review");
  const user = useUser();
  const { state, reload } = useAsync(() => api.listReviewQueue(user), [user.id]);

  return (
    <>
      <PageHeading
        title="For review"
        description="Choose category and urgency"
      />

      {state.status === "loading" && <Loading label="Loading" />}

      {state.status === "error" && (
        <ErrorState description={state.message} onRetry={reload} />
      )}

      {state.status === "ready" &&
        (state.data.items.length === 0 ? (
          <EmptyState
            title="Nothing to check"
            description="Everything routed on its own"
          />
        ) : (
          <RequestTable items={state.data.items} caption="Requests waiting to be checked" />
        ))}
    </>
  );
}
