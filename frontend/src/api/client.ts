import * as fx from "./fixtures";
import type { OwnedNotification } from "./fixtures";
import type {
  Category,
  Notification,
  Paginated,
  RequestStatus,
  RequestSummary,
  Role,
  RoutingRule,
  ServiceRequest,
  Urgency,
  User,
} from "./types";
import { URGENCY_ORDER } from "./types";

// Fixture-backed stand-in for the API. Covers the operations the prototype's
// seven screens need, not all of openapi.yaml, and returns the same shapes, so
// swapping this file for real fetch calls does not touch the screens.
//
// `signIn` checks the email only. The real endpoint posts credentials and gets
// back a session cookie, so the login screen is the one screen that changes when
// the backend lands.
//
// Role scoping is applied here too. On the real system it is enforced
// server-side and this layer would not be trusted. But the prototype has to
// *show* the scoping rules, and one that displays another resident's request
// would demo a system that leaks.

const LATENCY_MS = 320;

const delay = <T>(value: T): Promise<T> =>
  new Promise((resolve) => setTimeout(() => resolve(value), LATENCY_MS));

let store: ServiceRequest[] = [...fx.requests];
let notices: OwnedNotification[] = [...fx.notifications];
let nextId = 44;
let nextHistoryId = 100_000;
let nextNotificationId = 500;

export const getCategories = () =>
  delay(fx.categories.filter((c) => c.is_active));

// Every account, and the only list sign in reads. Registering adds to this, and
// deactivating here is what stops someone signing in. Divina is included because
// she handles six of the eighteen fixtures, so leaving her out made a third of
// the sample data unreachable.
let people: User[] = [...Object.values(fx.users), fx.otherStaff];

// The four seeded accounts, for the list on the sign-in screen. Does not grow
// with registrations, which is the point.
export const accounts = [...people];

const active = (u: User) => u.is_active;

// Synchronous, for restoring a signed-in user on first render. Same
// normalisation as sign in, so both lookups agree.
export const userByEmail = (email: string): User | undefined =>
  people.find((u) => u.email === email.trim().toLowerCase() && active(u));

// Email decides the account. The password is not checked until the backend
// exists, but a deactivated account is refused, so the admin control works.
export const signIn = (email: string): Promise<User | null> =>
  delay(userByEmail(email) ?? null);

const toSummary = (r: ServiceRequest): RequestSummary => ({
  id: r.id,
  reference_number: r.reference_number,
  description: r.description,
  category: r.category,
  urgency: r.urgency,
  category_confidence: r.category_confidence,
  urgency_confidence: r.urgency_confidence,
  status: r.status,
  assigned_staff: r.assigned_staff,
  created_at: r.created_at,
});

// The scope clause from GET /api/requests. The routing-rule half is omitted
// because auto-routing sets `assigned_staff`, so in the prototype the two coincide and
// no fixture defines routing rules.
const visibleTo = (r: ServiceRequest, user: User): boolean => {
  if (user.role === "admin") return true;
  if (user.role === "staff") {
    return r.assigned_staff?.id === user.id || r.status === "under_review";
  }
  return r.citizen.id === user.id;
};

const rank = (r: ServiceRequest) =>
  r.urgency ? URGENCY_ORDER[r.urgency] : URGENCY_ORDER.low + 1;

export type ListParams = {
  status?: RequestStatus[];
  urgency?: Urgency;
  categoryId?: number;
  limit?: number;
  offset?: number;
};

export const listRequests = (
  user: User,
  params: ListParams = {},
): Promise<Paginated<RequestSummary>> => {
  const { limit = 20, offset = 0 } = params;

  const matched = store
    .filter((r) => visibleTo(r, user))
    .filter((r) => !params.status?.length || params.status.includes(r.status))
    .filter((r) => !params.urgency || r.urgency === params.urgency)
    .filter((r) => !params.categoryId || r.category?.id === params.categoryId);

  // Ordering is role-dependent and chosen by the server. A citizen wants their
  // newest request first; a staff queue is worked highest-urgency, oldest-first.
  matched.sort(
    user.role === "citizen"
      ? (a, b) => Date.parse(b.created_at) - Date.parse(a.created_at)
      : (a, b) =>
          rank(a) - rank(b) ||
          Date.parse(a.created_at) - Date.parse(b.created_at),
  );

  return delay({
    items: matched.slice(offset, offset + limit).map(toSummary),
    total: matched.length,
    limit,
    offset,
  });
};

// Out-of-scope resolves to null, not an error, matching the API's decision to
// return 404 rather than 403 so ids cannot be probed.
export const getRequest = (
  user: User,
  id: number,
): Promise<ServiceRequest | null> => {
  const found = store.find((r) => r.id === id && visibleTo(r, user));
  return delay(found ?? null);
};

// Object URLs so an uploaded photo can actually be opened in the prototype. The
// API stores files server-side and serves them by id, so this map goes away
// with the swap to fetch.
const files = new Map<number, string>();
export const attachmentUrl = (id: number) => files.get(id);

let nextAttachmentId = 900;

export const ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp", "application/pdf"];
export const MAX_FILE_BYTES = 5 * 1024 * 1024;

export const submitRequest = (
  user: User,
  description: string,
  uploads: File[] = [],
): Promise<ServiceRequest> => {
  const now = new Date().toISOString();
  const id = nextId++;
  const actor = { id: user.id, full_name: user.full_name, role: user.role };
  const created: ServiceRequest = {
    id,
    reference_number: `GAB-2026-${String(id).padStart(5, "0")}`,
    citizen: actor,
    description,
    // Null on purpose: the API returns immediately with status `submitted` and
    // classifies afterwards, so the citizen never waits on inference.
    predicted_category: null,
    predicted_urgency: null,
    category_confidence: null,
    urgency_confidence: null,
    final_category: null,
    final_urgency: null,
    category: null,
    urgency: null,
    status: "submitted",
    assigned_staff: null,
    model_version: null,
    classified_at: null,
    created_at: now,
    updated_at: now,
    resolved_at: null,
    attachments: uploads.map((file) => {
      const id = nextAttachmentId++;
      files.set(id, URL.createObjectURL(file));
      return {
        id,
        filename: file.name,
        mime_type: file.type,
        size_bytes: file.size,
        uploaded_at: now,
      };
    }),
    status_history: [
      {
        id: nextHistoryId++,
        from_status: null,
        to_status: "submitted",
        actor,
        note: null,
        created_at: now,
      },
    ],
  };
  store = [created, ...store];
  return delay(created);
};

// Oldest first, not urgency first. The urgency shown here came from a prediction
// the system was not confident about, so ordering by it would trust the number
// this queue exists to doubt.
export const listReviewQueue = async (
  user: User,
): Promise<Paginated<RequestSummary>> => {
  const page = await listRequests(user, { status: ["under_review"] });
  return {
    ...page,
    items: [...page.items].sort(
      (a, b) => Date.parse(a.created_at) - Date.parse(b.created_at),
    ),
  };
};

export const updateStatus = (
  user: User,
  id: number,
  to: "in_progress" | "resolved" | "closed",
  note: string,
): Promise<ServiceRequest | null> => {
  const target = store.find((r) => r.id === id && visibleTo(r, user));
  if (!target) return delay(null);

  const now = new Date().toISOString();
  const updated: ServiceRequest = {
    ...target,
    status: to,
    updated_at: now,
    resolved_at: to === "resolved" || to === "closed" ? now : target.resolved_at,
    status_history: [
      ...target.status_history,
      {
        id: nextHistoryId++,
        from_status: target.status,
        to_status: to,
        actor: { id: user.id, full_name: user.full_name, role: user.role },
        note: note.trim() || null,
        created_at: now,
      },
    ],
  };
  store = store.map((r) => (r.id === id ? updated : r));
  return delay(updated);
};

// Works on any visible request, not just the review queue. The case where
// correction matters most is a confident wrong prediction, which never reaches
// the queue.
//
// Returns the updated request, exactly as the real endpoint does. Callers detect
// a handoff by comparing `assigned_staff` before and after; a bespoke result
// shape here would have no equivalent after the swap to fetch.
export const reclassify = (
  user: User,
  id: number,
  category: Category,
  urgency: Urgency,
  note: string,
): Promise<ServiceRequest | null> => {
  const target = store.find((r) => r.id === id && visibleTo(r, user));
  // Re-routing a finished request would resurrect it into an active queue.
  if (!target || target.status === "resolved" || target.status === "closed") {
    return delay(null);
  }

  const now = new Date().toISOString();
  const handler = fx.routing[category.id];
  const movedAway = target.assigned_staff?.id !== handler.id;
  const wasUnderReview = target.status === "under_review";

  const updated: ServiceRequest = {
    ...target,
    // predicted_* is deliberately untouched. The gap between what the model said
    // and what the human chose is the correction record.
    final_category: category,
    final_urgency: urgency,
    category,
    urgency,
    status: "routed",
    // Changing the category re-runs routing, which can hand the request to a
    // different officer, after which the corrector no longer sees it.
    assigned_staff: handler,
    updated_at: now,
    status_history: wasUnderReview
      ? [
          ...target.status_history,
          {
            id: nextHistoryId++,
            from_status: "under_review" as const,
            to_status: "routed" as const,
            actor: { id: user.id, full_name: user.full_name, role: user.role },
            note: note.trim() || `Set to ${category.name} / ${urgency}`,
            created_at: now,
          },
        ]
      : target.status_history,
  };
  store = store.map((r) => (r.id === id ? updated : r));

  if (movedAway) {
    notices = [
      ...notices,
      {
        userId: target.citizen.id,
        notification: {
          id: nextNotificationId++,
          request_id: target.id,
          reference_number: target.reference_number,
          message: "Your request went to another office",
          is_read: false,
          created_at: now,
        },
      },
    ];
  }

  return delay(updated);
};

export const listNotifications = (
  user: User,
): Promise<Paginated<Notification> & { unread_count: number }> => {
  const mine = notices
    .filter((n) => n.userId === user.id)
    .map((n) => n.notification)
    .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));

  return delay({
    items: mine,
    total: mine.length,
    limit: 20,
    offset: 0,
    unread_count: mine.filter((n) => !n.is_read).length,
  });
};

export const markNotificationRead = (
  user: User,
  id: number,
): Promise<Notification | null> => {
  const owned = notices.find(
    (n) => n.notification.id === id && n.userId === user.id,
  );
  if (!owned) return delay(null);

  const updated = { ...owned.notification, is_read: true };
  notices = notices.map((n) =>
    n.notification.id === id && n.userId === user.id
      ? { ...n, notification: updated }
      : n,
  );
  return delay(updated);
};

// ---------------------------------------------------------------- admin ----

let rules = { ...fx.routing };
const auditRows = [...fx.auditLog];
let nextUserSuffix = 5;

export const listUsers = (): Promise<User[]> => delay([...people]);

// Live lookup. `accounts` is the frozen snapshot for the sign-in list and must
// not be used for this.
export const findPerson = (id: string) => people.find((p) => p.id === id);

// An admin who demotes or deactivates the last active admin locks everyone out
// of account management. The API returns 409 for this; the UI refuses too so
// the operator finds out before they click.
export const isLastActiveAdmin = (user: User) =>
  user.role === "admin" &&
  people.filter((p) => p.role === "admin" && p.is_active).length === 1;

export type UserDraft = { full_name: string; email: string; role: Role };

export const createUser = (draft: UserDraft): Promise<User | null> => {
  if (people.some((p) => p.email === draft.email.trim().toLowerCase())) {
    return delay(null);
  }
  const created: User = {
    id: `8f1c1d2e-0000-4000-8000-${String(nextUserSuffix++).padStart(12, "0")}`,
    email: draft.email.trim().toLowerCase(),
    full_name: draft.full_name.trim(),
    role: draft.role,
    is_active: true,
    created_at: new Date().toISOString(),
  };
  people = [...people, created];
  return delay(created);
};

export const updateUser = (
  id: string,
  patch: Partial<Pick<User, "role" | "is_active">>,
): Promise<User | null> => {
  const target = people.find((p) => p.id === id);
  if (!target) return delay(null);
  const wouldStrandAdmins =
    isLastActiveAdmin(target) &&
    (patch.is_active === false || (patch.role && patch.role !== "admin"));
  if (wouldStrandAdmins) return delay(null);

  const updated = { ...target, ...patch };
  people = people.map((p) => (p.id === id ? updated : p));
  return delay(updated);
};

export const listRoutingRules = (): Promise<RoutingRule[]> =>
  delay(
    fx.categories.map((category, i) => ({
      id: i + 1,
      category,
      staff: rules[category.id],
      is_active: true,
    })),
  );

// One handler per category, so routing stays deterministic. The schema enforces
// the same thing with a partial unique index.
export const setRoutingRule = (
  categoryId: number,
  staffId: string,
): Promise<boolean> => {
  const handler = people.find((p) => p.id === staffId);
  if (!handler) return delay(false);
  rules = {
    ...rules,
    [categoryId]: {
      id: handler.id,
      full_name: handler.full_name,
      role: handler.role,
    },
  };
  return delay(true);
};

export type AuditFilters = { actorId?: string; action?: string };

export const listAuditLog = (filters: AuditFilters = {}) => {
  const matched = auditRows
    .filter((r) => !filters.actorId || r.actor?.id === filters.actorId)
    .filter((r) => !filters.action || r.action === filters.action)
    .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));
  return delay(matched);
};

export const auditActions = [...new Set(fx.auditLog.map((r) => r.action))];

export const register = (draft: UserDraft): Promise<User | null> =>
  createUser({ ...draft, role: "citizen" });
