import { fullDate } from "./format";
import type { RequestSummary, ServiceRequest } from "../api/types";

// What a resident sees. Same stored status as the staff wording, said the way a
// person would say it.
//
// Received, Sorted and With {name} are the three events the paper promises the
// citizen is notified about: received, categorized, routed.
//
// This is a function, not a map, because `routed` needs the name of whoever has
// it and a fallback for when nobody is set yet.

type Sliceable = Pick<
  ServiceRequest | RequestSummary,
  "status" | "assigned_staff"
>;

export function citizenStatus(request: Sliceable): string {
  switch (request.status) {
    case "submitted":
      return "Received";
    case "classified":
      return "Sorted";
    case "routed":
      return request.assigned_staff
        ? `With ${request.assigned_staff.full_name}`
        : "Sent to the right office";
    case "under_review":
      return "Being checked";
    case "in_progress":
      return "Being worked on";
    // Resolved and closed are different records but mean the same thing to a
    // resident. Two badges that feel identical read like a downgrade, so the
    // difference lives on the detail screen where there is room to say it.
    case "resolved":
    case "closed":
      return "Done";
  }
}

// The extra line under the status on the detail screen, where the difference
// between resolved and closed is worth spelling out.
export function citizenStatusNote(request: ServiceRequest): string | null {
  if (request.status === "resolved") {
    return request.resolved_at
      ? `Done on ${fullDate(request.resolved_at)}`
      : "Done";
  }
  if (request.status === "closed") {
    return "Closed, no more updates";
  }
  return null;
}
