import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import api from "../services/api";

function Register() {
  const navigate = useNavigate();

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  function validate() {
    if (!name.trim() || !email.trim() || !password || !confirmPassword) {
      return "Please fill in all fields.";
    }
    if (password !== confirmPassword) {
      return "Passwords do not match.";
    }
    if (password.length < 8 || new TextEncoder().encode(password).length > 72) {
      return "Password must be 8-72 UTF-8 bytes.";
    }
    return "";
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");

    const validationError = validate();
    if (validationError) {
      setError(validationError);
      return;
    }

    setIsLoading(true);
    try {
      // Matches the backend's UserRegister schema exactly:
      // { name, email, password, role } — role is omitted here so
      // the backend applies its own default ("user").
      await api.post("/auth/register", { name, email, password });

      navigate("/login", {
        replace: true,
        state: { successMessage: "Registration successful! Please log in." },
      });
    } catch (err) {
      const detail = err.response?.data?.detail;
      if (typeof detail === "string") {
        // e.g. "Email already registered"
        setError(detail);
      } else if (Array.isArray(detail) && detail.length > 0) {
        // FastAPI validation errors (422) come back as a list of
        // { msg, loc, ... } objects instead of a plain string.
        setError(detail[0].msg || "Please check the form and try again.");
      } else {
        setError("Something went wrong. Please try again.");
      }
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#f5f7fb] px-4 py-8">
      <div className="grid w-full max-w-4xl overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-xl shadow-slate-200/60 md:grid-cols-[0.9fr_1.1fr]">
        <div className="hidden bg-slate-900 p-10 text-white md:block">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-500 text-sm font-bold">
            SS
          </div>
          <p className="mt-16 text-sm font-medium text-brand-200">Join a better way to resolve issues</p>
          <h1 className="mt-3 text-3xl font-bold leading-tight">
            Your voice matters.
            <br />
            Make it count.
          </h1>
          <p className="mt-5 text-sm leading-6 text-slate-300">
            Create an account to submit complaints, follow updates, and help build a more responsive community.
          </p>
          <div className="mt-10 space-y-3 text-sm text-slate-300">
            <p><span className="mr-2 text-brand-300">✓</span>Track every resolution in one place</p>
            <p><span className="mr-2 text-brand-300">✓</span>Get timely status notifications</p>
          </div>
        </div>

        <div className="p-6 sm:p-10">
          <p className="text-sm font-semibold text-brand-600">Get started</p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900">Create your account</h1>
          <p className="mt-2 text-sm text-slate-500">It only takes a minute to join Samadhan Setu.</p>

          <form onSubmit={handleSubmit} className="mt-6 space-y-4">
            <div>
              <label htmlFor="name" className="block text-sm font-medium text-slate-700">Full name</label>
              <input
                id="name"
                type="text"
                required
                autoComplete="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Enter your full name"
                className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm shadow-sm placeholder:text-slate-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
              />
            </div>

            <div>
              <label htmlFor="email" className="block text-sm font-medium text-slate-700">Email address</label>
              <input
                id="email"
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm shadow-sm placeholder:text-slate-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-slate-700">Password</label>
              <div className="relative mt-1">
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  required
                  minLength={8}
                  maxLength={72}
                  autoComplete="new-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Create a password"
                  className="w-full rounded-xl border border-slate-200 px-3 py-2.5 pr-16 text-sm shadow-sm placeholder:text-slate-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((visible) => !visible)}
                  className="absolute inset-y-0 right-3 text-xs font-semibold text-slate-500 hover:text-brand-600"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? "Hide" : "Show"}
                </button>
              </div>
              <p className="mt-1.5 text-xs text-slate-400">Use a password you do not use elsewhere.</p>
            </div>

            <div>
              <label htmlFor="confirmPassword" className="block text-sm font-medium text-slate-700">Confirm password</label>
              <input
                id="confirmPassword"
                type={showPassword ? "text" : "password"}
                required
                autoComplete="new-password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Re-enter your password"
                className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm shadow-sm placeholder:text-slate-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
              />
            </div>

            {error && (
              <p className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={isLoading}
              className="w-full rounded-xl bg-brand-600 py-2.5 text-sm font-semibold text-white shadow-sm hover:-translate-y-0.5 hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:translate-y-0"
            >
              {isLoading ? "Creating account..." : "Create account"}
            </button>
          </form>

          <p className="mt-5 text-center text-sm text-slate-500">
            Already have an account?{" "}
            <Link to="/login" className="font-semibold text-brand-600 hover:text-brand-700 hover:underline">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}

export default Register;
