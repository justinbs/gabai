import * as fx from "./fixtures";
import type { OwnedNotification } from "./fixtures";
import type {
  Category,
  Notification,
  Paginated,
  RequestStatus,
  RequestSummary,
  Role,
  ServiceRequest,
  Urgency,
  User,
} from "./types";
import { URGENCY_ORDER } from "./types";

// Fixture-backed stand-in for the API. Covers the operations the prototype's
// seven screens need — not all of openapi.yaml — and returns the same shapes, so
// swapping this file for real fetch calls does not touch the screens.
//
// One exception: `login` takes a role, not credentials. The role switcher is
// deliberate (it is how a demo and a respondent task scenario move between
// roles), so the login screen is the one screen that changes at swap time.
//
// Role scoping is applied here too. On the real system it is enforced
// server-side and this layer would not be trusted — but the prototype has to
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

export const login = (role: Role): Promise<User> => delay(fx.users[role]);

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

// The scope clause from GET /api/requests. The routing-rule half is omitted:
// auto-routing sets `assigned_staff`, so in the prototype the two coincide and
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

export const submitRequest = (
  user: User,
  description: string,
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
    attachments: [],
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

export const listReviewQueue = (
  user: User,
): Promise<Paginated<RequestSummary>> =>
  listRequests(user, { status: ["under_review"] });

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

export type ReclassifyResult =
  | { ok: true; request: ServiceRequest; reassignedTo: string | null }
  | { ok: false; reason: "not_found" | "finished" };

// Works on any visible request, not just the review queue — the case where
// correction matters most is a confident wrong prediction, which never reaches
// the queue.
export const reclassify = (
  user: User,
  id: number,
  category: Category,
  urgency: Urgency,
  note: string,
): Promise<ReclassifyResult> => {
  const target = store.find((r) => r.id === id && visibleTo(r, user));
  if (!target) return delay({ ok: false as const, reason: "not_found" as const });
  if (target.status === "resolved" || target.status === "closed") {
    // Re-routing a finished request would resurrect it into an active queue.
    return delay({ ok: false as const, reason: "finished" as const });
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
    // different officer — after which the corrector no longer sees it.
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
            note: note.trim() || `Labelled ${category.name} / ${urgency}.`,
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
          message: "Your request has been reassigned to another office.",
          is_read: false,
          created_at: now,
        },
      },
    ];
  }

  return delay({
    ok: true as const,
    request: updated,
    reassignedTo: movedAway ? handler.full_name : null,
  });
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

export const resetFixtures = () => {
  store = [...fx.requests];
  notices = [...fx.notifications];
  nextId = 44;
  nextHistoryId = 100_000;
  nextNotificationId = 500;
};
