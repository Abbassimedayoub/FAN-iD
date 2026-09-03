import { httpClient } from "@/lib/httpClient";

export async function logoutWeb(accessToken?: string): Promise<void> {
  await httpClient.post(
    "/api/v1/auth/logout",
    undefined,
    accessToken
      ? {
          headers: {
            Authorization: `Bearer ${accessToken}`,
          },
        }
      : undefined,
  );
}
