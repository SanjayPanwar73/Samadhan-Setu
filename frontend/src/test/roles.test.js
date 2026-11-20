import { describe, it, expect, beforeEach } from "vitest";
import {
  canonicalRole,
  getHomeRouteForRole,
  getSafeReturnPath,
  getSessionClaims,
  hasRole,
  roleLabel,
} from "../utils/auth";

function token(role, overrides = {}) {
  return `eyJhbGciOiJIUzI1NiJ9.${btoa(JSON.stringify({ sub: "3", role, exp: Math.floor(Date.now() / 1000) + 1000, ...overrides }))}.sig`;
}

describe("V2 roles", () => {
  it("maps V1 role names onto V2 names and leaves V2 names alone", () => {
    expect(canonicalRole("user")).toBe("student");
    expect(canonicalRole("admin")).toBe("super_admin");
    expect(canonicalRole("management")).toBe("hod");
    for (const r of ["student", "staff", "dept_admin", "hod", "super_admin"]) expect(canonicalRole(r)).toBe(r);
    expect(canonicalRole(null)).toBeNull();
  });

  it("hasRole accepts either naming and rejects everything else", () => {
    expect(hasRole("user", "student")).toBe(true);
    expect(hasRole("student", "user")).toBe(true);
    expect(hasRole("admin", "super_admin")).toBe(true);
    expect(hasRole("dept_admin", "super_admin")).toBe(false);
    expect(hasRole("staff", "dept_admin", "hod")).toBe(false);
    expect(hasRole(null, "student")).toBe(false);
    expect(hasRole(undefined)).toBe(false);
  });

  it("every role has its own home and unknown roles go to login", () => {
    expect(getHomeRouteForRole("student")).toBe("/complaints");
    expect(getHomeRouteForRole("staff")).toBe("/tasks");
    expect(getHomeRouteForRole("dept_admin")).toBe("/department");
    expect(getHomeRouteForRole("hod")).toBe("/hod");
    expect(getHomeRouteForRole("super_admin")).toBe("/super/users");
    expect(getHomeRouteForRole("user")).toBe("/complaints");
    expect(getHomeRouteForRole("nope")).toBe("/login");
  });

  it("accepts a session for each V2 and legacy role but rejects unknown ones", () => {
    for (const r of ["student", "staff", "dept_admin", "hod", "super_admin", "user", "admin", "management"])
      expect(getSessionClaims(token(r))).not.toBeNull();
    expect(getSessionClaims(token("root"))).toBeNull();
    expect(getSessionClaims(token("hod", { exp: 1 }))).toBeNull();
  });

  it("only returns people to pages their role may open", () => {
    expect(getSafeReturnPath("/tasks/12", "staff")).toBe("/tasks/12");
    expect(getSafeReturnPath("/tasks/12", "student")).toBeNull();
    expect(getSafeReturnPath("/department/issues/5", "dept_admin")).toBe("/department/issues/5");
    expect(getSafeReturnPath("/department/issues/5", "staff")).toBeNull();
    expect(getSafeReturnPath("/department/issues/5", "hod")).toBeNull();
    expect(getSafeReturnPath("/hod", "hod")).toBe("/hod");
    expect(getSafeReturnPath("/super/config", "super_admin")).toBe("/super/config");
    expect(getSafeReturnPath("/super/config", "dept_admin")).toBeNull();
    expect(getSafeReturnPath("/complaints/new", "student")).toBe("/complaints/new");
    expect(getSafeReturnPath("/notifications", "hod")).toBe("/notifications");
    for (const bad of ["//evil.test", "https://evil.test", "/tasks/0", "/tasks/abc", "/super/../x"])
      expect(getSafeReturnPath(bad, "super_admin")).toBeNull();
  });

  it("labels roles for display", () => {
    expect(roleLabel("dept_admin")).toBe("Department admin");
    expect(roleLabel("user")).toBe("Student");
    expect(roleLabel("???")).toBe("Account");
  });
});
