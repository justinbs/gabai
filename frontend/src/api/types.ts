import type { components } from "./schema";

// Aliases over the generated schema. Screens import from here, never from
// schema.d.ts, so a regeneration that renames something breaks in one file.
type S = components["schemas"];

export type Role = S["Role"];
export type ApprovalStatus = S["ApprovalStatus"];
export type VerificationMethod = S["VerificationMethod"];
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
export type SiteSettings = S["SiteSettings"];
export type Location = S["Location"];
export type LocationUpdate = S["LocationUpdate"];
export type DuplicateSuggestion = S["DuplicateSuggestion"];
export type Surge = S["Surge"];
export type SiteSettingsUpdate = S["SiteSettingsUpdate"];
export type ThemePreset = S["ThemePreset"];
export type CategoryUpdate = S["CategoryUpdate"];

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

export const VERIFICATION_LABELS: Record<VerificationMethod, string> = {
  id_in_person: "Valid ID, shown in person",
  personally_known: "I know them personally",
  barangay_record: "Checked barangay records",
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
  "request.submitted": "Request submitted",
  "request.status_changed": "Status changed",
  "request.flagged_urgent": "Marked urgent by resident",
  "request.linked": "Linked to another report",
  "request.unlinked": "Link removed",
  "request.duplicate_dismissed": "Marked not a duplicate",
  "routing_rules.replaced": "Routing changed",
  "user.created": "Account added",
  "user.signed_in": "Signed in",
  "user.sign_in_failed": "Sign-in failed",
  "user.sign_in_locked": "Sign-in locked after too many tries",
  "user.deactivated": "Account deactivated",
  "user.reactivated": "Account reactivated",
  "user.password_reset": "Password reset",
  "user.approved": "Resident approved",
  "user.rejected": "Resident turned down",
  "user.role_changed": "Role changed",
  "user.renamed": "Name changed",
  "user.terms_accepted": "Terms accepted",
  "site.updated": "Site details changed",
  "site.logo_changed": "Logo changed",
  "site.logo_removed": "Logo removed",
  "category.updated": "Category changed",
  "location.created": "Place added",
  "location.updated": "Place changed",
  "retention.applied": "Old personal data removed",
};

export const URGENCY_LABELS: Record<Urgency, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
};
