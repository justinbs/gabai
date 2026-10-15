import * as api from "../api/client";
import { RequestTable } from "../components/RequestTable";
import { EmptyState, ErrorState, Help, Loading, PageHeading } from "../components/ui";
import { useAsync } from "../lib/useAsync";
import { usePageTitle } from "../lib/usePageTitle";
import { useUser } from "../session-context";

export function Referred() {
  usePageTitle("Referred");
  const user = useUser();
  const { state, reload } = useAsync(
    () => api.listRequests(user, { status: ["referred"] }),
    [user.id],
  );

  return (
    <>
      <PageHeading title="Referred" description="Concerns sent to another agency" />
      <Help>
        <p>These belong to another agency, such as Meralco or the water provider. The resident was told whom to contact.</p>
        <p>Open one to close it once it's settled, or to take it back if the barangay should handle it.</p>
      </Help>

      {state.status === "loading" && <Loading />}
      {state.status === "error" && <ErrorState description={state.message} onRetry={reload} />}
      {state.status === "ready" &&
        (state.data.items.length === 0 ? (
          <EmptyState title="Nothing referred" description="Referred concerns show up here" />
        ) : (
          <RequestTable items={state.data.items} caption="Referred requests" />
        ))}
    </>
  );
}