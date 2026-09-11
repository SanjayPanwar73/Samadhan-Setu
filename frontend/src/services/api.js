import axios from "axios";
import { getToken, logout } from "../utils/auth";

const api = axios.create({
  baseURL:
    import.meta.env.VITE_API_URL ||
    import.meta.env.VITE_API_BASE_URL ||
    "http://localhost:8000",
  timeout: 60_000,
});

const PUBLIC_AUTH_PATHS = new Set([
  "/auth/login",
  "/auth/register",
  "/auth/token",
]);

api.interceptors.request.use((config) => {
  const token = getToken();
  if (token && !PUBLIC_AUTH_PATHS.has(config.url))
    config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    // /auth/me is protected too. Ignore a late 401 from an older session after
    // another tab or a new sign-in has already changed the current token.
    if (
      error.response?.status === 401 &&
      !PUBLIC_AUTH_PATHS.has(error.config?.url)
    ) {
      const rejectedToken = error.config?.headers?.Authorization?.replace(
        /^Bearer /,
        "",
      );
      if (rejectedToken && rejectedToken === getToken()) logout();
    }
    return Promise.reject(error);
  },
);

export function getApiError(
  error,
  fallback = "Something went wrong. Please try again.",
) {
  if (error?.code === "ECONNABORTED" || error?.code === "ETIMEDOUT") {
    return "This is taking longer than expected. Please try again in a moment.";
  }
  if (!error?.response && error?.isAxiosError) {
    return "Unable to connect to the service. Check your connection and try again.";
  }
  const data = error?.response?.data;
  const errors = Array.isArray(data?.errors)
    ? data.errors
    : Array.isArray(data?.detail)
      ? data.detail
      : [];
  const messages = errors
    .slice(0, 3)
    .map((item) => {
      if (typeof item?.msg !== "string") return null;
      const field = Array.isArray(item.loc)
        ? item.loc
            .filter((part) => !["body", "query", "path"].includes(part))
            .join(" ")
            .replaceAll("_", " ")
        : "";
      return `${field ? `${field.charAt(0).toUpperCase()}${field.slice(1)}: ` : ""}${item.msg.replace(/^Value error, /, "")}`;
    })
    .filter(Boolean);
  if (messages.length) return messages.join(". ");
  if (typeof data?.detail === "string") return data.detail;
  return fallback;
}

export default api;
