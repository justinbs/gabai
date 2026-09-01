import { Link } from "react-router-dom";

import * as api from "../api/client";
import { RequestList } from "../components/RequestList";
import { Button, EmptyState, ErrorState, Loading, PageHeading } from "../components/ui";
import { useAsync } from "../lib/useAsync";
import { usePageTitle } from "../lib/usePageTitle";
import { useUser } from "../session-context";

export function MyRequests() {
  usePageTitle("My requests");
  const user = useUser();
  const { state, reload } = useAsync(() => api.listRequests(user), [user.id]);

  return (
    <>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <PageHeading title="My requests" />
        <Link to="/submit">
          <Button>Report a concern</Button>
        </Link>
      </div>

      {state.status === "loading" && <Loading label="Loading" />}

      {state.status === "error" && (
        <ErrorState description={state.message} onRetry={reload} />
      )}

      {state.status === "ready" &&
        (state.data.items.length === 0 ? (
          <EmptyState
            title="Nothing here yet"
            description="Anything you report shows up here"
            action={
              <Link to="/submit">
                <Button>Report a concern</Button>
              </Link>
            }
          />
        ) : (
          <RequestList items={state.data.items} />
        ))}
    </>
  );
}
