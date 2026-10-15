import * as api from "../api/client";
import { RequestTable } from "../components/RequestTable";
import { Link } from "react-router-dom";
import { EmptyState, ErrorState, FOCUS_LINK, Help, Loading, PageHeading } from "../components/ui";
import { useAsync } from "../lib/useAsync";
import { usePageTitle } from "../lib/usePageTitle";
import { useUser } from "../session-context";
import type { Surge } from "../api/types";

// Highest urgency first, then oldest. That is the order the queue is worked.
// Sorting, not a separate pipeline: urgency changes position, never routing.
export function StaffQueue() {
  usePageTitle("Queue");
  const user = useUser();
  const { state, reload } = useAsync(
    () =>
      api.listRequests(user, {
        status: ["routed", "in_progress", "classified", "resolved"],
      }),
    [user.id],
  );
  const surges = useAsync(() => api.listSurges(), [user.id]);

  return (
    <>
      <PageHeading title="Queue" />
      <Help>
        <p>These are the requests assigned to you and those in the categories you handle, highest urgency first and oldest first within each level.</p>
        <p>Open a request to move it along: in progress, then resolved, then closed. A note you add is sent to the resident. Resolved requests stay at the bottom until you close them.</p>
        <p>If the category or urgency is wrong, correct it on the request. It moves to the person who handles the new category.</p>
        <p>When several residents report the same problem, link the newer reports to the first one on its page. They leave the queue and follow it.</p>
        <p>If a concern belongs to another agency, use "Refer to another agency" on its page. It moves to Referred.</p>
      </Help>

      {surges.state.status === "ready" && surges.state.data.length > 0 && (
        <SurgeNotice surges={surges.state.data} />
      )}

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
          <RequestTable items={state.data.items} caption="Requests not yet closed" />
        ))}
    </>
  );
}

// Many reports about one problem in the last hour, usually one incident.
function SurgeNotice({ surges }: { surges: Surge[] }) {
  return (
    <div role="status" className="mb-6 border-l-4 border-danger py-1 pl-4">
      {surges.map((surge) => (
        <p key={`${surge.category.id}-${surge.location?.id ?? "any"}`}>
          <span className="font-bold">
            {surge.count} reports about {surge.category.name}
            {surge.location ? ` in ${surge.location.name}` : ""} in the last hour
          </span>{" "}
          ·{" "}
          {surge.main ? (
            <Link to={`/requests/${surge.main.id}#same-problem`} className={`text-link underline ${FOCUS_LINK}`}>
              Check and link them together
            </Link>
          ) : (
            "Still being sorted"
          )}
        </p>
      ))}
    </div>
  );
}
