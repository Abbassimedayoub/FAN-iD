import { httpClient } from "@/lib/httpClient";

export function eventImageUrl(value: string | null | undefined): string | null {
  if (!value) {
    return null;
  }

  if (
    value.startsWith("http://") ||
    value.startsWith("https://") ||
    value.startsWith("blob:") ||
    value.startsWith("data:")
  ) {
    return value;
  }

  const baseURL = httpClient.defaults.baseURL;

  if (!baseURL) {
    return value;
  }

  try {
    const normalizedBase = baseURL.endsWith("/") ? baseURL : `${baseURL}/`;

    const absoluteBase = new URL(normalizedBase, window.location.origin);

    return new URL(value.replace(/^\/+/, ""), absoluteBase.origin).toString();
  } catch {
    return value;
  }
}
