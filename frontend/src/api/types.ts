import type { components } from "./schema";

// Aliases over the generated schema. Screens import from here, never from
// schema.d.ts, so a regeneration that renames something breaks in one file.
type S = components["schemas"];

export type Role = S["Role"];
export type Urgency = S["Urgency"];
export type RequestStatus = S["RequestStatus"];
export type Category = S["Category"];
export type User = S["User"];
export type UserSummary = S["UserSummary"];
export type StatusHistoryEntry = S["StatusHistoryEntry"];
export type Attachment = S["Attachment"];
export type Notification = S["Notification"];
export type RequestSummary = S["RequestSummary"];

// Named ServiceRequest, not Request — `Request` is a DOM global and shadowing it
// produces genuinely confusing type errors.
export type ServiceRequest = S["Request"];

export type Paginated<T> = { items: T[]; total: number; limit: number; offset: number };

export const URGENCY_ORDER: Record<Urgency, number> = { high: 0, medium: 1, low: 2 };

export const STATUS_LABELS: Record<RequestStatus, string> = {
  submitted: "Submitted",
  classified: "Classified",
  routed: "Routed",
  under_review: "For review",
  in_progress: "In progress",
  resolved: "Resolved",
  closed: "Closed",
};

export const URGENCY_LABELS: Record<Urgency, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
};
