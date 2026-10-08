import { ApiError, http } from "./http";
import type {
  AuditLogEntry,
  Category,
  CategoryUpdate,
  Notification,
  Paginated,
  RequestStatus,
  RequestSummary,
  Role,
  RoutingRule,
  ServiceRequest,
  SiteSettings,
  SiteSettingsUpdate,
  Urgency,
  User,
} from "./types";

// Everything below now talks to the real backend. No fixture data left.

// Lists come back 100 rows at a time at most, so the screens read every page.
async function everyPage<T>(url: (offset: number) => string): Promise<Paginated<T>> {
  const items: T[] = [];
  for (;;) {
    const page = await http.get<Paginated<T>>(url(items.length));
    items.push(...page.items);
    if (page.items.length === 0 || items.length >= page.total) {
      return { items, total: page.total, limit: items.length, offset: 0 };
    }
  }
}

// ---------------------------------------------------------------- auth ----

export const signIn = async (email: string, password: string): Promise<boolean> => {
  const body = new URLSearchParams();
  body.set("username", email.trim().toLowerCase());
  body.set("password", password);
  try {
    await http.postForm<void>("/api/auth/login", body);
    return true;
  } catch {
    return false;
  }
};

export const signOut = async (): Promise<void> => {
  try {
    await http.post<void>("/api/auth/logout");
  } catch {
    // Already signed out server-side is fine too.
  }
};

export const getCurrentUser = async (): Promise<User | null> => {
  try {
    return await http.get<User>("/api/auth/me");
  } catch {
    return null;
  }
};

export const register = async (draft: {
  full_name: string;
  email: string;
  password: string;
  residence: string;
  terms_version: string;
}): Promise<User | null> => {
  try {
    return await http.post<User>("/api/auth/register", {
      email: draft.email.trim().toLowerCase(),
      password: draft.password,
      full_name: draft.full_name.trim(),
      residence: draft.residence.trim(),
      terms_version: draft.terms_version,
    });
  } catch (err) {
    // 409 means the email is taken, unless the terms changed while the page was
    // open, which is thrown for the screen to show. A 422 is the password policy
    // and carries its own message.
    if (err instanceof ApiError && err.status === 409 && err.message === "TERMS_OUTDATED") throw err;
    if (err instanceof ApiError && (err.status === 409 || err.status === 400)) {
      return null;
    }
    throw err;
  }
};

// Throws ApiError 409 when the version isn't current, meaning the page is stale.
export const acceptTerms = (version: string) => http.post<User>("/api/auth/terms", { version });

// Throws ApiError: 400 wrong current password, 422 new one fails the policy.
export const changePassword = (currentPassword: string, newPassword: string) =>
  http.put<void>("/api/auth/password", {
    current_password: currentPassword,
    new_password: newPassword,
  });

// All four are the auth library's routes. The two "send" ones are always 202,
// whether or not the address has an account.
export const requestPasswordEmail = (email: string) =>
  http.post<void>("/api/auth/forgot-password", { email: email.trim().toLowerCase() });

// Throws ApiError 400: message is RESET_PASSWORD_BAD_TOKEN, or a policy reason.
export const setPasswordFromLink = (token: string, password: string) =>
  http.post<void>("/api/auth/reset-password", { token, password });

export const requestVerifyEmail = (email: string) =>
  http.post<void>("/api/auth/request-verify-token", { email: email.trim().toLowerCase() });

// Throws ApiError 400: VERIFY_USER_BAD_TOKEN or VERIFY_USER_ALREADY_VERIFIED.
export const verifyEmail = (token: string) =>
  http.post<User>("/api/auth/verify", { token });

// ---------------------------------------------------------- categories ----

export const getCategories = (): Promise<Category[]> =>
  http.get<Category[]>("/api/categories");

// -------------------------------------------------------------- files -----

export const ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp", "application/pdf"];
export const MAX_FILE_BYTES = 5 * 1024 * 1024;

export const attachmentUrl = (requestId: number, attachmentId: number) =>
  `/api/requests/${requestId}/attachments/${attachmentId}`;

// ------------------------------------------------------------ requests ----

export type ListParams = {
  status?: RequestStatus[];
  urgency?: Urgency;
  categoryId?: number;
  limit?: number;
  offset?: number;
};

export const listRequests = async (
  _user: User,
  params: ListParams = {},
): Promise<Paginated<RequestSummary>> => {
  const query = new URLSearchParams();
  if (params.urgency) query.set("urgency", params.urgency);
  if (params.categoryId) query.set("category_id", String(params.categoryId));
  params.status?.forEach((s) => query.append("status", s));
  if (params.limit) {
    query.set("limit", String(params.limit));
    if (params.offset) query.set("offset", String(params.offset));
    return http.get<Paginated<RequestSummary>>(`/api/requests?${query.toString()}`);
  }
  // No limit given: the whole list, as the queue and My requests screens need.
  return everyPage<RequestSummary>((offset) => {
    const page = new URLSearchParams(query);
    page.set("limit", "100");
    page.set("offset", String(offset));
    return `/api/requests?${page.toString()}`;
  });
};

export const getRequest = async (
  _user: User,
  id: number,
): Promise<ServiceRequest | null> => {
  try {
    return await http.get<ServiceRequest>(`/api/requests/${id}`);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null;
    throw err;
  }
};

// The request is created first, then each file is sent on its own, so the page
// can show progress and retry only the files that failed.
export const createRequest = (description: string): Promise<ServiceRequest> =>
  http.post<ServiceRequest>("/api/requests", { description });

export const uploadAttachment = async (requestId: number, file: File): Promise<void> => {
  const form = new FormData();
  form.set("file", file);
  await http.postForm<unknown>(`/api/requests/${requestId}/attachments`, form);
};

export const listReviewQueue = (): Promise<Paginated<RequestSummary>> =>
  everyPage<RequestSummary>((offset) => `/api/review-queue?limit=100&offset=${offset}`);

export const updateStatus = async (
  _user: User,
  id: number,
  to: "in_progress" | "resolved" | "closed",
  note: string,
): Promise<ServiceRequest | null> => {
  try {
    return await http.patch<ServiceRequest>(`/api/requests/${id}/status`, {
      to_status: to,
      note: note.trim() || undefined,
    });
  } catch (err) {
    if (err instanceof ApiError && [403, 404, 409].includes(err.status)) return null;
    throw err;
  }
};

export const reclassify = async (
  _user: User,
  id: number,
  category: Category,
  urgency: Urgency,
  note: string,
): Promise<ServiceRequest | null> => {
  try {
    return await http.patch<ServiceRequest>(`/api/requests/${id}/classification`, {
      final_category_id: category.id,
      final_urgency: urgency,
      note: note.trim() || undefined,
    });
  } catch (err) {
    if (err instanceof ApiError && [403, 404, 409].includes(err.status)) return null;
    throw err;
  }
};

// ------------------------------------------------------- notifications ----

export const listNotifications = (): Promise<Paginated<Notification> & { unread_count: number }> =>
  http.get<Paginated<Notification> & { unread_count: number }>(
    "/api/notifications?limit=20",
  );

export const markNotificationRead = async (
  _user: User,
  id: number,
): Promise<Notification | null> => {
  try {
    return await http.patch<Notification>(`/api/notifications/${id}/read`);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null;
    throw err;
  }
};

// ------------------------------------------------------- registrations ----

export const listRegistrations = async (
  status: "pending" | "rejected" = "pending",
): Promise<User[]> => {
  const page = await http.get<Paginated<User>>(
    `/api/registrations?status=${status}&limit=100`,
  );
  return page.items;
};

// Throws ApiError 409 with the reason: already approved, or email not
// confirmed yet. 404 when it isn't a resident's account.
export const decideRegistration = (id: string, decision: "approved" | "rejected") =>
  http.patch<User>(`/api/registrations/${id}`, { approval_status: decision });

// ------------------------------------------------------- admin: users -----

export type UserDraft = { full_name: string; email: string; password: string; role: Role };

// Every account, 100 per page (the server's maximum).
export const listUsers = async (): Promise<User[]> => {
  const users: User[] = [];
  for (;;) {
    const page = await http.get<{ items: User[]; total: number; limit: number; offset: number }>(
      `/api/admin/users?limit=100&offset=${users.length}`,
    );
    users.push(...page.items);
    if (page.items.length === 0 || users.length >= page.total) return users;
  }
};

export const createUser = async (draft: UserDraft): Promise<User | null> => {
  try {
    return await http.post<User>("/api/admin/users", {
      email: draft.email.trim().toLowerCase(),
      password: draft.password,
      full_name: draft.full_name.trim(),
      role: draft.role,
    });
  } catch (err) {
    if (err instanceof ApiError && err.status === 409) return null;
    throw err;
  }
};

export const resetPassword = async (id: string): Promise<string> => {
  const body = await http.post<{ temporary_password: string }>(
    `/api/admin/users/${id}/password`,
  );
  return body.temporary_password;
};

export const updateUser = async (
  id: string,
  patch: Partial<Pick<User, "full_name" | "role" | "is_active">>,
): Promise<User | null> => {
  try {
    return await http.patch<User>(`/api/admin/users/${id}`, patch);
  } catch (err) {
    if (err instanceof ApiError && [404, 409].includes(err.status)) return null;
    throw err;
  }
};

// ------------------------------------------------------ admin: routing ----

export const listRoutingRules = (): Promise<RoutingRule[]> =>
  http.get<RoutingRule[]>("/api/admin/routing-rules");

export const replaceRoutingRules = async (
  rules: { categoryId: number; staffId: string }[],
): Promise<RoutingRule[] | null> => {
  try {
    return await http.put<RoutingRule[]>("/api/admin/routing-rules", {
      rules: rules.map((r) => ({ category_id: r.categoryId, staff_id: r.staffId })),
    });
  } catch (err) {
    if (err instanceof ApiError && err.status === 409) return null;
    throw err;
  }
};

// ------------------------------------------------------- admin: audit -----

export type AuditFilters = { actorId?: string; action?: string };

export const listAuditLog = async (filters: AuditFilters = {}) => {
  const query = new URLSearchParams();
  if (filters.actorId) query.set("actor_id", filters.actorId);
  if (filters.action) query.set("action", filters.action);
  const all = await everyPage<AuditLogEntry>((offset) => {
    const page = new URLSearchParams(query);
    page.set("limit", "100");
    page.set("offset", String(offset));
    return `/api/admin/audit-log?${page.toString()}`;
  });
  return all.items;
};

// ---------------------------------------------------------------- site ----

// Public. The masthead and footer need it before anyone signs in.
export const getSite = () => http.get<SiteSettings>("/api/site");

export const updateSite = (changes: SiteSettingsUpdate) =>
  http.patch<SiteSettings>("/api/admin/site", changes);

// Throws ApiError 413 over 1 MB, 415 when it isn't a PNG, JPEG or WebP.
export const uploadLogo = (file: File) => {
  const form = new FormData();
  form.set("file", file);
  return http.putForm<SiteSettings>("/api/admin/site/logo", form);
};

export const removeLogo = () => http.del<SiteSettings>("/api/admin/site/logo");

export const LOGO_TYPES = ["image/png", "image/jpeg", "image/webp"];
export const MAX_LOGO_BYTES = 1024 * 1024;

// ---------------------------------------------------- admin: categories ----

export const listAllCategories = () => http.get<Category[]>("/api/admin/categories");

// Throws ApiError 409 when it would switch off the last category that's on.
export const updateCategory = (id: number, changes: CategoryUpdate) =>
  http.patch<Category>(`/api/admin/categories/${id}`, changes);
