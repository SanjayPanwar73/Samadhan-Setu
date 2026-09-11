import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import api, { getApiError } from "../services/api";
import {
  AUTH_CHANGE_EVENT,
  getSessionClaims,
  getToken,
  logout,
  setToken,
} from "../utils/auth";

const AuthContext = createContext(null);
let identity = { token: null, user: null, promise: null };

function loadIdentity(token, force = false) {
  if (identity.token === token) {
    if (identity.promise) return identity.promise;
    if (identity.user && !force) return Promise.resolve(identity.user);
  }
  const resource = { token, user: null, promise: null };
  resource.promise = api
    .get("/auth/me")
    .then(({ data }) => {
      resource.user = data;
      return data;
    })
    .finally(() => {
      resource.promise = null;
    });
  identity = resource;
  return resource.promise;
}

export function AuthProvider({ children }) {
  const [token, updateToken] = useState(getToken);
  const [user, setUser] = useState(() =>
    identity.token === token ? identity.user : null,
  );
  const [loading, setLoading] = useState(
    () => Boolean(getSessionClaims(token)) && !user,
  );
  const [error, setError] = useState("");

  const refreshUser = useCallback(async ({ force = true } = {}) => {
    const currentToken = getToken();
    if (!getSessionClaims(currentToken)) {
      setUser(null);
      setLoading(false);
      setError("");
      return null;
    }
    setLoading(true);
    setError("");
    try {
      const profile = await loadIdentity(currentToken, force);
      if (getToken() === currentToken) setUser(profile);
      return profile;
    } catch (requestError) {
      if (getToken() === currentToken)
        setError(
          getApiError(
            requestError,
            "We couldn't load your account. Please try again.",
          ),
        );
      return null;
    } finally {
      if (getToken() === currentToken) setLoading(false);
    }
  }, []);

  useEffect(() => {
    const syncSession = () => {
      const currentToken = getToken();
      updateToken(currentToken);
      if (identity.token !== currentToken)
        identity = { token: currentToken, user: null, promise: null };
      setUser(identity.user);
      setError("");
      setLoading(Boolean(getSessionClaims(currentToken)) && !identity.user);
    };
    const onStorage = (event) => {
      if (event.key === "token" || event.key === null) syncSession();
    };
    window.addEventListener(AUTH_CHANGE_EVENT, syncSession);
    window.addEventListener("storage", onStorage);
    return () => {
      window.removeEventListener(AUTH_CHANGE_EVENT, syncSession);
      window.removeEventListener("storage", onStorage);
    };
  }, []);

  useEffect(() => {
    const claims = getSessionClaims(token);
    if (!claims) {
      if (token) logout();
      return;
    }
    // The module-level resource shares StrictMode's duplicate mount request
    // and keeps the shell and profile page on the same server identity.
    let active = true;
    queueMicrotask(() => {
      if (active) void refreshUser({ force: false });
    });
    let expiryTimer;
    const checkExpiry = () => {
      const remaining = claims.exp * 1000 - Date.now();
      if (remaining <= 0) {
        if (getToken() === token) logout();
        return;
      }
      expiryTimer = window.setTimeout(
        checkExpiry,
        Math.min(remaining, 2_147_483_647),
      );
    };
    checkExpiry();
    return () => {
      active = false;
      window.clearTimeout(expiryTimer);
    };
  }, [token, refreshUser]);

  const completeLogin = useCallback((session) => {
    if (!getSessionClaims(session.access_token))
      throw new Error("The server returned an invalid session.");
    identity = {
      token: session.access_token,
      user: session.user || null,
      promise: null,
    };
    setToken(session.access_token);
  }, []);

  const value = useMemo(
    () => ({
      user,
      role: user?.role || getSessionClaims(token)?.role || null,
      loading,
      error,
      refreshUser,
      completeLogin,
      signOut: logout,
    }),
    [user, token, loading, error, refreshUser, completeLogin],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// The provider and its consumer hook intentionally share one context module.
// oxlint-disable-next-line react/only-export-components
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
