import { useEffect, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import api, { getApiError } from "../services/api";
import { useAuth } from "../contexts/AuthContext";
import { getHomeRouteForRole } from "../utils/auth";
import AuthLayout from "../components/AuthLayout";
import PasswordInput from "../components/PasswordInput";
import Icon from "../components/Icon";
import { Alert, Button, Field } from "../components/ui";

export default function Register() {
  const navigate = useNavigate();
  const { role } = useAuth();
  const [form, setForm] = useState({
    name: "",
    email: "",
    password: "",
    confirm: "",
  });
  const [errors, setErrors] = useState({});
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    document.title = "Create account · Samadhan Setu";
  }, []);
  if (role) return <Navigate to={getHomeRouteForRole(role)} replace />;
  function update(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: "" }));
  }
  async function submit(event) {
    event.preventDefault();
    if (loading) return;
    const invalid = {};
    if (!form.name.trim()) invalid.name = "Enter your full name.";
    if (form.password.length < 8)
      invalid.password = "Use at least 8 characters.";
    if (new TextEncoder().encode(form.password).length > 72)
      invalid.password = "This password is too long. Use fewer characters.";
    if (form.confirm !== form.password)
      invalid.confirm = "Your passwords don’t match.";
    setErrors(invalid);
    setError("");
    if (Object.keys(invalid).length) {
      document.getElementById(Object.keys(invalid)[0])?.focus();
      return;
    }
    setLoading(true);
    try {
      await api.post("/auth/register", {
        name: form.name.trim(),
        email: form.email.trim(),
        password: form.password,
      });
      navigate("/login", {
        replace: true,
        state: {
          successMessage: "Your account is ready. Sign in to get started.",
        },
      });
    } catch (requestError) {
      setError(
        getApiError(
          requestError,
          "We couldn’t create your account. Please try again.",
        ),
      );
    } finally {
      setLoading(false);
    }
  }
  return (
    <AuthLayout register>
      <p className="eyebrow">A fresh start</p>
      <h1 className="text-3xl font-semibold tracking-[-.045em] text-brand-900">
        Make your voice count.
      </h1>
      <p className="mt-3 text-sm leading-6 text-slate-500">
        Create an account to raise concerns and follow their progress.
      </p>
      <form className="mt-7 space-y-4" onSubmit={submit}>
        <Field label="Full name" htmlFor="name" error={errors.name}>
          <input
            id="name"
            name="name"
            autoComplete="name"
            className="input"
            placeholder="Your full name"
            required
            maxLength={120}
            value={form.name}
            onChange={(event) => update("name", event.target.value)}
            aria-invalid={Boolean(errors.name)}
            aria-describedby={errors.name ? "name-error" : undefined}
            disabled={loading}
          />
        </Field>
        <Field label="Email address" htmlFor="email">
          <input
            id="email"
            name="email"
            autoComplete="email"
            type="email"
            className="input"
            placeholder="you@example.com"
            required
            value={form.email}
            onChange={(event) => update("email", event.target.value)}
            disabled={loading}
          />
        </Field>
        <Field
          label="Password"
          htmlFor="password"
          hint="At least 8 characters. Choose a password you don’t use elsewhere."
          error={errors.password}
        >
          <PasswordInput
            id="password"
            name="password"
            autoComplete="new-password"
            required
            minLength={8}
            maxLength={72}
            placeholder="Create a password"
            value={form.password}
            onChange={(event) => update("password", event.target.value)}
            aria-invalid={Boolean(errors.password)}
            aria-describedby={`password-hint${errors.password ? " password-error" : ""}`}
            disabled={loading}
          />
        </Field>
        <Field
          label="Confirm password"
          htmlFor="confirm"
          error={errors.confirm}
        >
          <PasswordInput
            id="confirm"
            name="confirm"
            autoComplete="new-password"
            required
            maxLength={72}
            placeholder="Enter your password again"
            value={form.confirm}
            onChange={(event) => update("confirm", event.target.value)}
            aria-invalid={Boolean(errors.confirm)}
            aria-describedby={errors.confirm ? "confirm-error" : undefined}
            disabled={loading}
          />
        </Field>
        {error && <Alert variant="error">{error}</Alert>}
        <Button type="submit" loading={loading} className="w-full !min-h-11">
          {loading ? "Creating your account…" : "Create account"}
          {!loading && <Icon name="arrowRight" size={16} />}
        </Button>
      </form>
      <p className="mt-6 text-center text-xs text-slate-500">
        Already have an account?{" "}
        <Link
          to="/login"
          className="font-semibold text-brand-600 hover:underline"
        >
          Sign in
        </Link>
      </p>
    </AuthLayout>
  );
}
