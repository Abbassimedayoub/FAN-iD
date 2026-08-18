import { describe, expect, it } from "vitest";

import { toAppError } from "./errors";

describe("toAppError", () => {
  it("classifies a network error (no response) as 'network'", () => {
    const result = toAppError({});
    expect(result.errorClass).toBe("network");
    expect(result.code).toBe("NETWORK_ERROR");
  });

  it("classifies a 401 as 'auth'", () => {
    const result = toAppError({
      response: { status: 401, data: { error: { code: "NOT_AUTHENTICATED", message: "x" } } },
    });
    expect(result.errorClass).toBe("auth");
  });

  it("classifies a 409 with a business code as 'business' and preserves the code", () => {
    const result = toAppError({
      response: {
        status: 409,
        data: {
          error: {
            code: "STOCK_UNAVAILABLE",
            message: "Il ne reste que 2 places.",
            details: { available: 2 },
          },
        },
      },
    });
    expect(result.errorClass).toBe("business");
    expect(result.code).toBe("STOCK_UNAVAILABLE");
    expect(result.details).toEqual({ available: 2 });
  });

  it("classifies a 5xx as 'server'", () => {
    const result = toAppError({ response: { status: 500, data: {} } });
    expect(result.errorClass).toBe("server");
  });
});
