import { jwtDecode } from "jwt-decode";

export const AUTH_CHANGE_EVENT = "samadhan:session-change";
export const ROLE_HOME_ROUTES = {
  user: "/complaints",
  staff: "/staff",
  admin: "/admin",
  management: "/management",
};

export function getToken() {
  try {
    return localStorage.getItem("token");
  } catch {
    return null;
  }
}

// Claims inform navigation only. The API remains responsible for verifying
// the token signature and authorizing every request.
export function getSessionClaims(token = getToken()) {
  if (!token) return null;
  try {
    const claims = jwtDecode(token);
    const userId = Number(claims.sub);
    if (
      !Object.hasOwn(ROLE_HOME_ROUTES, claims.role) ||
      !Number.isFinite(claims.exp) ||
      claims.exp * 1000 <= Date.now() ||
      !Number.isSafeInteger(userId) ||
      userId <= 0
    )
      return null;
    return claims;
  } catch {
    return null;
  }
}

export function getRole() {
  return getSessionClaims()?.role ?? null;
}

export function getUserId() {
  const claims = getSessionClaims();
  return claims ? Number(claims.sub) : null;
}

export function isAuthenticated() {
  return Boolean(getSessionClaims());
}

export function setToken(token) {
  if (!getSessionClaims(token))
    throw new Error(
      "The server returned an invalid session. Please sign in again.",
    );
  localStorage.setItem("token", token);
  window.dispatchEvent(new Event(AUTH_CHANGE_EVENT));
}

export function logout() {
  try {
    localStorage.removeItem("token");
  } finally {
    window.dispatchEvent(new Event(AUTH_CHANGE_EVENT));
  }
}

export function getHomeRouteForRole(role) {
  return ROLE_HOME_ROUTES[role] || "/login";
}

export function getDisplayName(user) {
  return user?.name || user?.email?.split("@")[0] || "Your account";
}

export const ROLE_LABELS = {
  user: "Community member",
  staff: "Resolution staff",
  admin: "Administrator",
  management: "Management",
};

// Only known, locally hosted routes are eligible after sign-in. Never accept
// an external URL or send someone back to a page their role cannot access.
export function getSafeReturnPath(value, role) {
  if (
    typeof value !== "string" ||
    !value.startsWith("/") ||
    value.startsWith("//") ||
    [...value].some((char) => char === "\\" || char.charCodeAt(0) < 32)
  )
    return null;
  try {
    const url = new URL(value, window.location.origin);
    if (url.origin !== window.location.origin) return null;
    const path = url.pathname;
    const shared =
      ["/profile", "/notifications", "/dashboard"].includes(path) ||
      /^\/complaints\/[1-9]\d*$/.test(path);
    const personal =
      path === getHomeRouteForRole(role) ||
      (role === "user" && path === "/complaints/new") ||
      (role === "admin" &&
        ["/admin/departments", "/management"].includes(path));
    return shared || personal ? `${path}${url.search}${url.hash}` : null;
  } catch {
    return null;
  }
}
