import { ApiError, http } from "./http";

export interface TranslateResponse {
  translated: string;
  provider: string;
}

export async function translate(
  text: string,
  src: string,
  dst: string
): Promise<TranslateResponse> {
  if (!text.trim()) {
    throw new ApiError("empty", 400);
  }
  return http.post<TranslateResponse>("/api/translate", { text, src, dst });
}
