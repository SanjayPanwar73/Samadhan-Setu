import { useEffect, useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import api, { getApiError } from "../services/api";
import { getHomeRouteForRole, getSafeReturnPath } from "../utils/auth";
import { useAuth } from "../contexts/AuthContext";
import AuthLayout from "../components/AuthLayout";
import PasswordInput from "../components/PasswordInput";
import Icon from "../components/Icon";
import { Alert, Button, Field } from "../components/ui";

export default function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  const { role, completeLogin } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    document.title = "Sign in · Samadhan Setu";
  }, []);
  if (role)
    return (
      <Navigate
        to={
          getSafeReturnPath(location.state?.from, role) ||
          getHomeRouteForRole(role)
        }
        replace
      />
    );
  async function submit(event) {
    event.preventDefault();
    if (loading) return;
    setError("");
    if (new TextEncoder().encode(password).length > 72) {
      setError("Password is too long. Use no more than 72 bytes.");
      return;
    }
    setLoading(true);
    try {
      const { data } = await api.post("/auth/login", {
        email: email.trim(),
        password,
      });
      completeLogin(data);
      const nextRole = data.user?.role || data.role;
      navigate(
        getSafeReturnPath(location.state?.from, nextRole) ||
          getHomeRouteForRole(nextRole),
        { replace: true },
      );
    } catch (requestError) {
      setError(
        requestError.response?.status === 401
          ? "The email or password is incorrect. Please try again."
          : getApiError(
              requestError,
              "We couldn’t sign you in. Please try again.",
            ),
      );
    } finally {
      setLoading(false);
    }
  }
  return (
    <AuthLayout>
      <p className="eyebrow">Welcome to your workspace</p>
      <h1 className="text-3xl font-semibold tracking-[-.045em] text-brand-900">
        Welcome back.
      </h1>
      <p className="mt-3 text-sm leading-6 text-slate-500">
        Sign in to keep things moving forward.
      </p>
      {location.state?.successMessage && (
        <Alert variant="success" className="mt-6">
          {location.state.successMessage}
        </Alert>
      )}
      <form className="mt-8 space-y-5" onSubmit={submit}>
        <Field label="Email address" htmlFor="email">
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            className="input"
            placeholder="you@example.com"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            disabled={loading}
          />
        </Field>
        <Field label="Password" htmlFor="password">
          <PasswordInput
            id="password"
            name="password"
            autoComplete="current-password"
            required
            maxLength={72}
            placeholder="Enter your password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            disabled={loading}
          />
        </Field>
        {error && <Alert variant="error">{error}</Alert>}
        <Button type="submit" loading={loading} className="w-full !min-h-11">
          {loading ? "Signing in…" : "Sign in"}
          {!loading && <Icon name="arrowRight" size={16} />}
        </Button>
      </form>
      <p className="mt-6 text-center text-xs text-slate-500">
        New to Samadhan Setu?{" "}
        <Link
          to="/register"
          className="font-semibold text-brand-600 hover:underline"
        >
          Create an account
        </Link>
      </p>
      {import.meta.env.DEV &&
        import.meta.env.VITE_ENABLE_DEMO_ACCOUNTS === "true" && (
          <details className="mt-7 rounded-lg border border-slate-200 p-3 text-xs text-slate-500">
            <summary className="cursor-pointer font-medium">
              Development demo accounts
            </summary>
            <p className="mt-2 leading-5">
              Requires the backend demo seed. Password: password123.
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {["user", "staff", "admin", "management"].map((value) => (
                <Button
                  key={value}
                  variant="secondary"
                  className="!min-h-8 !px-2 !py-1 !text-xs capitalize"
                  onClick={() => {
                    setEmail(`${value}@example.com`);
                    setPassword("password123");
                    setError("");
                  }}
                >
                  {value}
                </Button>
              ))}
            </div>
          </details>
        )}
    </AuthLayout>
  );
}
