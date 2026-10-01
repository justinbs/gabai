import * as api from "../api/client";
import { RequestTable } from "../components/RequestTable";
import { EmptyState, ErrorState, Help, Loading, PageHeading } from "../components/ui";
import { useAsync } from "../lib/useAsync";
import { usePageTitle } from "../lib/usePageTitle";
import { useUser } from "../session-context";

// Oldest first, deliberately. This is a backlog, and the urgency shown here came
// from a prediction the system was not confident about, so sorting by it would be
// trusting the number the queue exists to doubt.
export function ReviewQueue() {
  usePageTitle("For review");
  const user = useUser();
  const { state, reload } = useAsync(() => api.listReviewQueue(), [user.id]);

  return (
    <>
      <PageHeading
        title="For review"
        description="Choose category and urgency"
      />
      <Help>
        <p>The system wasn't sure how to sort these, so a person decides. They're listed oldest first.</p>
        <p>Open a request, choose its category and urgency, and save. It goes to whoever handles that category.</p>
        <p>The urgency shown here is only the system's guess. Read the request before you trust it.</p>
      </Help>

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
