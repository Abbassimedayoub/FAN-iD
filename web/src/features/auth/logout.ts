import { httpClient } from "@/lib/httpClient";

export async function logoutWeb(): Promise<void> {
  await httpClient.post("/api/v1/auth/logout");
}
