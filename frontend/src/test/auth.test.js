import { describe, it, expect, vi } from "vitest";
import { AxiosError } from "axios";
import {
  getRole,
  getSessionClaims,
  getSafeReturnPath,
  getUserId,
  logout,
  setToken,
} from "../utils/auth";
import api, { getApiError } from "../services/api";

function token(overrides = {}) {
  return `eyJhbGciOiJIUzI1NiJ9.${btoa(JSON.stringify({ sub: "7", role: "user", exp: Math.floor(Date.now() / 1000) + 1000, ...overrides }))}.test`;
}

describe("session and API regressions", () => {
  it("rejects expired, malformed, missing-expiry, unknown-role and invalid-subject sessions", () => {
    expect(getSessionClaims("not-a-token")).toBeNull();
    for (const claims of [
      { exp: 0 },
      { exp: undefined },
      { role: "superuser" },
      { sub: "NaN" },
      { sub: "0" },
      { sub: "1.5" },
    ])
      expect(getSessionClaims(token(claims))).toBeNull();
  });
  it("supports all existing role homes while deriving the user subject", () => {
    setToken(token({ role: "staff" }));
    expect(getRole()).toBe("staff");
    expect(getUserId()).toBe(7);
    logout();
    expect(getRole()).toBeNull();
  });
  it("blocks external and role-inappropriate return URLs", () => {
    for (const path of [
      "//evil.test",
      "https://evil.test/",
      "/\\evil.test",
      "/admin",
      "/login",
    ])
      expect(getSafeReturnPath(path, "user")).toBeNull();
    expect(getSafeReturnPath("/complaints/8?section=priority", "user")).toBe(
      "/complaints/8?section=priority",
    );
    expect(getSafeReturnPath("/management", "admin")).toBe("/management");
  });
  it("clears a rejected /auth/me session without clearing a newer session", async () => {
    const original = api.defaults.adapter;
    const current = token();
    setToken(current);
    api.defaults.adapter = async (config) => {
      throw new AxiosError("Unauthorized", "ERR_BAD_REQUEST", config, null, {
        status: 401,
        data: {},
        config,
      });
    };
    await expect(api.get("/auth/me")).rejects.toThrow("Unauthorized");
    expect(getRole()).toBeNull();
    setToken(current);
    api.defaults.adapter = async (config) => {
      setToken(token({ sub: "8", role: "admin" }));
      throw new AxiosError("Unauthorized", "ERR_BAD_REQUEST", config, null, {
        status: 401,
        data: {},
        config,
      });
    };
    await expect(api.get("/complaints/me")).rejects.toThrow("Unauthorized");
    expect(getRole()).toBe("admin");
    api.defaults.adapter = original;
  });
  it("does not attach a stored token to public login requests", async () => {
    const original = api.defaults.adapter;
    setToken(token());
    const adapter = vi.fn(async (config) => ({
      data: {},
      status: 200,
      headers: {},
      config,
    }));
    api.defaults.adapter = adapter;
    await api.post("/auth/login", {
      email: "user@example.test",
      password: "password123",
    });
    expect(adapter.mock.calls[0][0].headers.Authorization).toBeUndefined();
    api.defaults.adapter = original;
  });
  it("renders both FastAPI validation formats as helpful strings", () => {
    const errors = [
      {
        loc: ["body", "people_affected"],
        msg: "Input should be greater than or equal to 1",
      },
    ];
    expect(
      getApiError({
        response: { data: { detail: "Request validation failed", errors } },
      }),
    ).toContain("People affected:");
    expect(getApiError({ response: { data: { detail: errors } } })).toContain(
      "greater than or equal to 1",
    );
    expect(
      getApiError(
        { response: { data: { detail: { unexpected: true } } } },
        "Safe fallback",
      ),
    ).toBe("Safe fallback");
  });
});
