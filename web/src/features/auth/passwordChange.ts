import { httpClient } from "@/lib/httpClient";

export interface PasswordChangePayload {
  current_password: string;
  new_password: string;
}

export async function changePassword(payload: PasswordChangePayload): Promise<void> {
  await httpClient.post("/api/v1/auth/password/change", payload);
}
