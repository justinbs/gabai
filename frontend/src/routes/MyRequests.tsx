import { Link } from "react-router-dom";

import * as api from "../api/client";
import { RequestList } from "../components/RequestList";
import { Button, EmptyState, ErrorState, Help, Loading, PageHeading } from "../components/ui";
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
        <Help title="What the statuses mean · Ano ang ibig sabihin">
          <p>Received: the barangay has your report. Sorted or Sent to the right office: the system placed it. Being checked: a staff member is sorting it.<span className="block text-muted">Received: natanggap na ng barangay. Sorted o Sent to the right office: nailagay na ng sistema. Being checked: inaayos ito ng isang staff.</span></p>
          <p>With (name): that staff member is handling it. Being worked on: action has started. Done: it's resolved or closed.<span className="block text-muted">With (pangalan): ang staff na iyon ang humahawak. Being worked on: inaaksiyunan na. Done: tapos na.</span></p>
          <p>Open a request to see its full history and any notes from staff.<span className="block text-muted">Buksan ang request para makita ang buong kasaysayan at mga tala ng staff.</span></p>
        </Help>
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
