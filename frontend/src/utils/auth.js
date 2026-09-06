import { jwtDecode } from "jwt-decode";

// Small set of helpers around the JWT stored in localStorage.
// Keeping this logic in one place means components never touch
// localStorage or the token's internals directly.

export function getToken() {
  return localStorage.getItem("token");
}

export function isAuthenticated() {
  return Boolean(getRole());
}

// Decodes the token and returns its role claim, or null if there's
// no token, or the token is malformed/expired.
export function getRole() {
  const token = getToken();
  if (!token) return null;

  try {
    const decoded = jwtDecode(token);

    // If the token carries an expiry, treat an expired token as
    // "no role" so callers fall through to the login redirect.
    if (decoded.exp && decoded.exp * 1000 < Date.now()) {
      return null;
    }

    return decoded.role ?? null;
  } catch {
    return null;
  }
}

// Where each role lands after login / when redirected away from a
// page they don't have access to.
export const ROLE_HOME_ROUTES = {
  user: "/complaints",
  staff: "/staff",
  admin: "/admin",
  management: "/management",
};

export function getHomeRouteForRole(role) {
  return ROLE_HOME_ROUTES[role] || "/login";
}

export function getDisplayName(user) {
  return user?.name || user?.email?.split("@")[0] || "User";
}

// Clears stored auth data. Used by the logout button, and mirrors
// what the Axios response interceptor does on a 401.
export function logout() {
  localStorage.removeItem("token");
}
