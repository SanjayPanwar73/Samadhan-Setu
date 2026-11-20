import { jwtDecode } from "jwt-decode";

export const AUTH_CHANGE_EVENT = "samadhan:session-change";

// V2 roles. The V1 names stay valid until the data backfill has renamed every account.
export const V1_TO_V2_ROLE = {
  user: "student",
  admin: "super_admin",
  management: "hod",
};
export const ROLE_HOME_ROUTES = {
  student: "/complaints",
  staff: "/tasks",
  dept_admin: "/department",
  hod: "/hod",
  super_admin: "/super/users",
  ...Object.fromEntries(
    Object.entries(V1_TO_V2_ROLE).map(([v1, v2]) => [
      v1,
      v2 === "student" ? "/complaints" : v2 === "hod" ? "/hod" : "/super/users",
    ]),
  ),
};

export function canonicalRole(role) {
  return V1_TO_V2_ROLE[role] || role || null;
}

/** True when `role` (V1 or V2 name) is one of `allowed` (V1 or V2 names). */
export function hasRole(role, ...allowed) {
  const current = canonicalRole(role);
  return Boolean(current) && allowed.some((r) => canonicalRole(r) === current);
}

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
  student: "Student",
  staff: "Resolution staff",
  dept_admin: "Department admin",
  hod: "Head of department",
  super_admin: "Super admin",
};

export function roleLabel(role) {
  return ROLE_LABELS[canonicalRole(role)] || "Account";
}

// Paths a signed-in role may be sent back to after login. Never accept an
// external URL or a page the role cannot open.
const ROLE_PATHS = {
  student: [/^\/complaints$/, /^\/complaints\/new$/, /^\/complaints\/[1-9]\d*$/],
  staff: [/^\/tasks$/, /^\/tasks\/[1-9]\d*$/],
  dept_admin: [
    /^\/department$/,
    /^\/department\/staff$/,
    /^\/department\/issues\/[1-9]\d*$/,
  ],
  hod: [/^\/hod$/, /^\/management$/, /^\/department\/staff$/],
  super_admin: [
    /^\/management$/,
    /^\/department$/,
    /^\/department\/staff$/,
    /^\/super\/(users|departments|locations-assets|config|audit)$/,
    /^\/department\/issues\/[1-9]\d*$/,
  ],
};

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
    const shared = ["/profile", "/notifications", "/dashboard"].includes(path);
    const own = (ROLE_PATHS[canonicalRole(role)] || []).some((re) =>
      re.test(path),
    );
    return shared || own ? `${path}${url.search}${url.hash}` : null;
  } catch {
    return null;
  }
}
