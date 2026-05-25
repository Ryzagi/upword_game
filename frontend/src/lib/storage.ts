import type { PlayerId, RoomCode, Token } from "../api/rooms";

const NICKNAME_KEY = "app.nickname";
const credKey = (code: RoomCode) => `app.room.${code.toUpperCase()}`;

export interface RoomCredentials {
  player_id: PlayerId;
  token: Token;
}

export function loadNickname(): string {
  try {
    return localStorage.getItem(NICKNAME_KEY) ?? "";
  } catch {
    return "";
  }
}

export function saveNickname(nickname: string): void {
  try {
    localStorage.setItem(NICKNAME_KEY, nickname);
  } catch {
    /* ignore quota / private-mode errors */
  }
}

export function loadCredentials(code: RoomCode): RoomCredentials | null {
  try {
    const raw = localStorage.getItem(credKey(code));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as RoomCredentials;
    if (typeof parsed.player_id !== "string" || typeof parsed.token !== "string") {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function saveCredentials(code: RoomCode, creds: RoomCredentials): void {
  try {
    localStorage.setItem(credKey(code), JSON.stringify(creds));
  } catch {
    /* ignore */
  }
}

export function clearCredentials(code: RoomCode): void {
  try {
    localStorage.removeItem(credKey(code));
  } catch {
    /* ignore */
  }
}
