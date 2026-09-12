import { describe, expect, it } from "vitest";

import { sanitizeErrorForLogging } from "./ErrorBoundary";

describe("sanitizeErrorForLogging", () => {
  it("redacts credentials before an error reaches console.error", () => {
    const error = new Error("Authorization: Bearer access-secret-value password=plain-password");

    const result = sanitizeErrorForLogging(error, "fanid_refresh=refresh-secret-value");

    const serialized = JSON.stringify(result);

    expect(serialized).not.toContain("access-secret-value");
    expect(serialized).not.toContain("plain-password");
    expect(serialized).not.toContain("refresh-secret-value");
    expect(serialized).toContain("***REDACTED***");
  });
});
