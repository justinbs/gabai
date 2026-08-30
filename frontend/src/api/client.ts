import * as fx from "./fixtures";
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

// Fixture-backed stand-in for the API. Every function here mirrors an operation
// in openapi.yaml and returns the same shape, so swapping this file for real
// fetch calls does not touch a single screen.
//
// Role scoping is applied here too. On the real system it is enforced
// server-side and this layer would not be trusted — but the prototype has to
// *show* the scoping rules, and getting them wrong here would demo a system
// that leaks.

const LATENCY_MS = 320;

const delay = <T>(value: T): Promise<T> =>
  new Promise((resolve) => setTimeout(() => resolve(value), LATENCY_MS));

let store: ServiceRequest[] = [...fx.requests];
let notices: Notification[] = [...fx.notifications];
let nextId = 44;

export type Session = { user: User; role: Role };

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

// Mirrors the scope clause documented on GET /api/requests. Staff see what is
// assigned to them plus everything under review — a request awaiting manual
// classification cannot be scoped by a category that does not exist yet.
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
    .filter((r) => !params.categoryId || r.category?.id === params.categoryId)
    .sort(
      (a, b) =>
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
  const created: ServiceRequest = {
    id,
    reference_number: `GAB-2026-${String(id).padStart(5, "0")}`,
    citizen: { id: user.id, full_name: user.full_name, role: user.role },
    description,
    // Everything below is null on purpose: the API returns immediately with
    // status `submitted` and classifies afterwards, so the citizen never waits
    // on inference.
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
        id: id * 10,
        from_status: null,
        to_status: "submitted",
        actor: { id: user.id, full_name: user.full_name, role: user.role },
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
  const target = store.find((r) => r.id === id);
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
        id: Date.now(),
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

export const submitReviewDecision = (
  user: User,
  id: number,
  category: Category,
  urgency: Urgency,
  note: string,
): Promise<ServiceRequest | null> => {
  const target = store.find((r) => r.id === id);
  if (!target) return delay(null);

  const now = new Date().toISOString();
  const updated: ServiceRequest = {
    ...target,
    // predicted_* is deliberately untouched. The gap between what the model said
    // and what the reviewer chose is the correction record.
    final_category: category,
    final_urgency: urgency,
    category,
    urgency,
    status: "routed",
    assigned_staff: { id: fx.users.staff.id, full_name: fx.users.staff.full_name, role: "staff" },
    updated_at: now,
    status_history: [
      ...target.status_history,
      {
        id: Date.now(),
        from_status: "under_review",
        to_status: "routed",
        actor: { id: user.id, full_name: user.full_name, role: user.role },
        note: note.trim() || `Labelled ${category.name} / ${urgency}.`,
        created_at: now,
      },
    ],
  };
  store = store.map((r) => (r.id === id ? updated : r));
  return delay(updated);
};

export const listNotifications = () => delay([...notices]);

export const markNotificationRead = (id: number) => {
  notices = notices.map((n) => (n.id === id ? { ...n, is_read: true } : n));
  return delay(notices.find((n) => n.id === id)!);
};

// Lets a demo start from a clean slate without a page reload.
export const resetFixtures = () => {
  store = [...fx.requests];
  notices = [...fx.notifications];
  nextId = 44;
};
