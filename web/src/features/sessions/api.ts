import { httpClient } from "@/lib/httpClient";

import type { AuthSession } from "./types";

export async function listSessions(): Promise<AuthSession[]> {
  const response = await httpClient.get<AuthSession[]>("/api/v1/auth/sessions");
  return response.data;
}

export async function revokeSession(sessionId: string): Promise<void> {
  await httpClient.delete<void>(`/api/v1/auth/sessions/${sessionId}`);
}
