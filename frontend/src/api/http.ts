/** Shape of structured errors the server returns under `detail.error`. */
export type ApiErrorCode = string;

export class ApiError extends Error {
  constructor(
    public readonly code: ApiErrorCode,
    public readonly status: number
  ) {
    super(code);
    this.name = "ApiError";
  }
}

async function request<T>(method: "GET" | "POST", path: string, body?: unknown): Promise<T> {
  const init: RequestInit = {
    method,
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  };
  let res: Response;
  try {
    res = await fetch(path, init);
  } catch {
    throw new ApiError("network_error", 0);
  }
  let data: unknown;
  try {
    data = await res.json();
  } catch {
    data = null;
  }
  if (!res.ok) {
    const code = extractErrorCode(data) ?? "unknown_error";
    throw new ApiError(code, res.status);
  }
  return data as T;
}

function extractErrorCode(payload: unknown): string | null {
  if (
    typeof payload === "object" &&
    payload !== null &&
    "detail" in payload &&
    typeof (payload as Record<string, unknown>).detail === "object" &&
    (payload as Record<string, unknown>).detail !== null
  ) {
    const detail = (payload as { detail: Record<string, unknown> }).detail;
    if (
      "error" in detail &&
      typeof detail.error === "object" &&
      detail.error !== null &&
      "code" in (detail.error as Record<string, unknown>)
    ) {
      return String((detail.error as Record<string, unknown>).code);
    }
  }
  return null;
}

export const http = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body),
};
