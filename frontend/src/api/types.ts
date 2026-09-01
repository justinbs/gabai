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
export type AuditLogEntry = S["AuditLogEntry"];
export type RoutingRule = S["RoutingRule"];
export type RequestSummary = S["RequestSummary"];

// Named ServiceRequest because `Request` is a DOM global, and shadowing it
// produces genuinely confusing type errors.
export type ServiceRequest = S["Request"];

export type Paginated<T> = { items: T[]; total: number; limit: number; offset: number };

export const URGENCY_ORDER: Record<Urgency, number> = { high: 0, medium: 1, low: 2 };

// Display cue only. The server owns the real routing gate, and the value it
// uses gets chosen from data by the threshold sweep, not picked here.
export const REVIEW_THRESHOLD = 0.7;

// Staff wording. Stays close to the API so the screen and the log agree.
export const STAFF_STATUS_LABELS: Record<RequestStatus, string> = {
  submitted: "Submitted",
  classified: "Classified",
  routed: "Routed",
  under_review: "For review",
  in_progress: "In progress",
  resolved: "Resolved",
  closed: "Closed",
};

export const ROLE_LABELS: Record<Role, string> = {
  citizen: "Resident",
  staff: "Staff",
  admin: "Admin",
};

// Audit actions are stored as slugs and read by people. The slug stays in the
// data, the label is what the screen shows.
export const AUDIT_ACTION_LABELS: Record<string, string> = {
  "request.auto_routed": "Routed automatically",
  "request.reclassified": "Category corrected",
  "request.status_changed": "Status changed",
  "routing_rules.replaced": "Routing changed",
  "user.created": "Account added",
  "user.deactivated": "Account deactivated",
  "user.role_changed": "Role changed",
};

export const URGENCY_LABELS: Record<Urgency, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
};
