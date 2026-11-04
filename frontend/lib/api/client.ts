/**
 * Typed fetch wrapper around NEXT_PUBLIC_API_BASE_URL.
 *
 * Stateless — the caller supplies the Clerk-minted bearer token via opts.token.
 * There is no in-memory token store, no cookie refresh flow, and no auto-retry
 * on 401; the useApi() hook in ./useApi handles token injection and sign-out.
 */

const BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export class ApiError extends Error {
  status: number;
  errorCode?: string;
  details?: unknown;
  constructor(
    message: string,
    opts: { status: number; errorCode?: string; details?: unknown },
  ) {
    super(message);
    this.name = "ApiError";
    this.status = opts.status;
    this.errorCode = opts.errorCode;
    this.details = opts.details;
  }
}

export interface ApiRequestOptions {
  method?: string;
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined | null>;
  headers?: Record<string, string>;
  signal?: AbortSignal;
  /** Bearer token to attach as Authorization. Omit for anonymous calls. */
  token?: string;
}

export function buildUrl(
  path: string,
  query?: ApiRequestOptions["query"],
): string {
  const url = new URL(path.startsWith("http") ? path : `${BASE_URL}${path}`);
  if (query) {
    for (const [k, v] of Object.entries(query)) {
      if (v === undefined || v === null || v === "") continue;
      url.searchParams.set(k, String(v));
    }
  }
  return url.toString();
}

export async function apiFetch<T>(
  path: string,
  opts: ApiRequestOptions = {},
): Promise<T> {
  const method = opts.method ?? "GET";
  const isFormData =
    typeof FormData !== "undefined" && opts.body instanceof FormData;
  const headers: Record<string, string> = { ...(opts.headers ?? {}) };
  if (opts.token) {
    headers["authorization"] = `Bearer ${opts.token}`;
  }
  if (opts.body !== undefined && !isFormData) {
    headers["content-type"] = headers["content-type"] ?? "application/json";
  }
  const r = await fetch(buildUrl(path, opts.query), {
    method,
    headers,
    body:
      opts.body === undefined
        ? undefined
        : isFormData
        ? (opts.body as FormData)
        : JSON.stringify(opts.body),
    signal: opts.signal,
  });
  if (r.status === 204) return undefined as T;
  const text = await r.text();
  const parsed: unknown = text ? safeJson(text) : undefined;
  if (!r.ok) {
    const errPayload = (parsed ?? {}) as {
      error_code?: string;
      message?: string;
      detail?: string;
    };
    throw new ApiError(
      errPayload.message ?? errPayload.detail ?? `HTTP ${r.status}`,
      {
        status: r.status,
        errorCode: errPayload.error_code,
        details: parsed,
      },
    );
  }
  return (parsed ?? undefined) as T;
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

/**
 * Stand-alone API object for callers that already have a token (e.g. server
 * code or callers wrapping it with their own auth logic). React components
 * should prefer useApi() from ./useApi.
 */
export const api = {
  get: <T>(path: string, opts: Omit<ApiRequestOptions, "method"> = {}) =>
    apiFetch<T>(path, { ...opts, method: "GET" }),
  post: <T>(path: string, opts: Omit<ApiRequestOptions, "method"> = {}) =>
    apiFetch<T>(path, { ...opts, method: "POST" }),
  put: <T>(path: string, opts: Omit<ApiRequestOptions, "method"> = {}) =>
    apiFetch<T>(path, { ...opts, method: "PUT" }),
  patch: <T>(path: string, opts: Omit<ApiRequestOptions, "method"> = {}) =>
    apiFetch<T>(path, { ...opts, method: "PATCH" }),
  delete: <T>(path: string, opts: Omit<ApiRequestOptions, "method"> = {}) =>
    apiFetch<T>(path, { ...opts, method: "DELETE" }),
};
