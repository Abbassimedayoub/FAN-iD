export const WEB_INACTIVITY_TIMEOUT_MS = 15 * 60 * 1000;

export const BROWSER_ACTIVITY_STORAGE_KEY = "fanid_web_last_activity";
export const BROWSER_SESSION_BLOCKED_STORAGE_KEY = "fanid_web_session_blocked";

function browserLocalStorage(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

export function readBrowserActivity(): number | null {
  const value = browserLocalStorage()?.getItem(BROWSER_ACTIVITY_STORAGE_KEY);

  if (!value) {
    return null;
  }

  const timestamp = Number(value);
  return Number.isFinite(timestamp) ? timestamp : null;
}

export function recordBrowserActivity(timestamp = Date.now()): void {
  browserLocalStorage()?.setItem(BROWSER_ACTIVITY_STORAGE_KEY, String(timestamp));
}

export function browserSessionHasTimedOut(
  timeoutMs: number,
  timestamp = Date.now(),
): boolean {
  const lastActivity = readBrowserActivity();

  return lastActivity !== null && timestamp - lastActivity >= timeoutMs;
}

export function markBrowserSessionBlocked(): void {
  const storage = browserLocalStorage();

  storage?.setItem(BROWSER_SESSION_BLOCKED_STORAGE_KEY, "1");
  storage?.removeItem(BROWSER_ACTIVITY_STORAGE_KEY);
}

export function clearBrowserSessionBlock(): void {
  browserLocalStorage()?.removeItem(BROWSER_SESSION_BLOCKED_STORAGE_KEY);
}

export function isBrowserSessionBlocked(): boolean {
  return browserLocalStorage()?.getItem(BROWSER_SESSION_BLOCKED_STORAGE_KEY) === "1";
}
