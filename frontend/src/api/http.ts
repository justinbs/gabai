export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function extractMessage(data: unknown, fallback: string): string {
  if (!data || typeof data !== "object") return fallback;
  const body = data as Record<string, unknown>;
  if (typeof body.detail === "string") return body.detail;
  if (body.detail && typeof body.detail === "object" && !Array.isArray(body.detail)) {
    const detail = body.detail as Record<string, unknown>;
    if (typeof detail.reason === "string") return detail.reason;
    if (typeof detail.code === "string") return detail.code;
  }
  if (Array.isArray(body.detail) && body.detail[0] && typeof body.detail[0] === "object") {
    const first = body.detail[0] as Record<string, unknown>;
    if (typeof first.msg === "string") return first.msg;
  }
  if (body.error && typeof body.error === "object") {
    const err = body.error as Record<string, unknown>;
    if (typeof err.message === "string") return err.message;
  }
  return fallback;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const isFormLike = init.body instanceof FormData || init.body instanceof URLSearchParams;

  const response = await fetch(path, {
    ...init,
    credentials: "include",
    headers: {
      ...(init.body && !isFormLike ? { "Content-Type": "application/json" } : {}),
      ...init.headers,
    },
  });

  if (response.status === 204) {
    return undefined as T;
  }

  const isJson = response.headers.get("content-type")?.includes("application/json");
  const data = isJson ? await response.json() : undefined;

  if (!response.ok) {
    throw new ApiError(response.status, extractMessage(data, "Something went wrong"));
  }

  return data as T;
}

export const http = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body: body ? JSON.stringify(body) : undefined }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PUT", body: body ? JSON.stringify(body) : undefined }),
  postForm: <T>(path: string, body: URLSearchParams | FormData) =>
    request<T>(path, { method: "POST", body }),
};