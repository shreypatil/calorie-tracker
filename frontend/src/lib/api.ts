/**
 * The single door to the backend.
 *
 * Everything the UI knows about HTTP lives here: the bearer token, the
 * refresh-on-401 retry, and turning the API's problem+json into an Error the
 * components can render. Nothing else in the app calls fetch.
 */

const API_BASE = "/api/v1";

const ACCESS_TOKEN_KEY = "ct.access_token";
const REFRESH_TOKEN_KEY = "ct.refresh_token";

export interface ProblemDetail {
  type: string;
  title: string;
  status: number;
  detail: string;
  errors: { field?: string; message: string; type?: string }[];
  request_id: string;
}

export class ApiError extends Error {
  readonly status: number;
  readonly problem: ProblemDetail | null;

  constructor(status: number, problem: ProblemDetail | null, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.problem = problem;
  }

  /** Field-level messages, ready to show under the inputs that caused them. */
  get fieldErrors(): Record<string, string> {
    const result: Record<string, string> = {};
    for (const item of this.problem?.errors ?? []) {
      if (item.field) result[item.field] = item.message;
    }
    return result;
  }
}

export const tokens = {
  get access() {
    return localStorage.getItem(ACCESS_TOKEN_KEY);
  },
  get refresh() {
    return localStorage.getItem(REFRESH_TOKEN_KEY);
  },
  set(access: string, refresh: string) {
    localStorage.setItem(ACCESS_TOKEN_KEY, access);
    localStorage.setItem(REFRESH_TOKEN_KEY, refresh);
  },
  clear() {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
  },
};

/** Notifies the app when the session ends, so it can route back to sign-in. */
type SessionEndedHandler = () => void;
let onSessionEnded: SessionEndedHandler = () => {};
export function setSessionEndedHandler(handler: SessionEndedHandler) {
  onSessionEnded = handler;
}

async function readProblem(response: Response): Promise<ProblemDetail | null> {
  try {
    return (await response.json()) as ProblemDetail;
  } catch {
    return null;
  }
}

async function rawRequest(path: string, init: RequestInit, token: string | null) {
  // FormData must set its own Content-Type — the browser adds the multipart
  // boundary, and overriding it produces an unparseable request body.
  const isFormData = init.body instanceof FormData;

  return fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...(init.body && !isFormData ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  });
}

/**
 * Refresh in flight, shared by every caller.
 *
 * Without this, a page that fires five queries at once on an expired token
 * would send five refreshes; four would use an already-rotated token and fail,
 * logging the user out mid-session.
 */
let refreshInFlight: Promise<boolean> | null = null;

async function refreshSession(): Promise<boolean> {
  const refreshToken = tokens.refresh;
  if (!refreshToken) return false;

  refreshInFlight ??= (async () => {
    try {
      const response = await rawRequest(
        "/auth/refresh",
        { method: "POST", body: JSON.stringify({ refresh_token: refreshToken }) },
        null,
      );
      if (!response.ok) return false;
      const data = await response.json();
      tokens.set(data.access_token, data.refresh_token);
      return true;
    } catch {
      return false;
    } finally {
      refreshInFlight = null;
    }
  })();

  return refreshInFlight;
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response = await rawRequest(path, init, tokens.access);

  if (response.status === 401 && tokens.refresh) {
    if (await refreshSession()) {
      response = await rawRequest(path, init, tokens.access);
    } else {
      tokens.clear();
      onSessionEnded();
    }
  }

  if (!response.ok) {
    const problem = await readProblem(response);
    throw new ApiError(
      response.status,
      problem,
      problem?.detail ?? `Request failed with status ${response.status}`,
    );
  }

  return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: JSON.stringify(body ?? {}) }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
  upload: <T>(path: string, file: File, field = "file") => {
    const form = new FormData();
    form.append(field, file);
    return request<T>(path, { method: "POST", body: form });
  },
};

/** Builds a query string, dropping empty values so URLs stay clean. */
export function query(params: Record<string, string | number | undefined | null>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.append(key, String(value));
    }
  }
  const result = search.toString();
  return result ? `?${result}` : "";
}
