import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import api from "../services/api";
import { getRole, getHomeRouteForRole } from "../utils/auth";

const DEMO_ACCOUNTS = [
  { label: "User", email: "user@example.com" },
  { label: "Staff", email: "staff@example.com" },
  { label: "Admin", email: "admin@example.com" },
  { label: "Management", email: "management@example.com" },
];

function Login() {
  const navigate = useNavigate();
  const location = useLocation();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const successMessage = location.state?.successMessage;

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setIsLoading(true);

    try {
      const response = await api.post("/auth/login", { email, password });

      // Store the JWT so future requests (via the Axios interceptor)
      // and route guards can use it.
      localStorage.setItem("token", response.data.access_token);

      // Use the role returned by the authenticated backend response for the
      // first redirect; the signed token remains the persisted auth state.
      const role = response.data.user?.role || response.data.role || getRole();
      navigate(getHomeRouteForRole(role), { replace: true });
    } catch (err) {
      if (err.response && err.response.status === 401) {
        setError("Incorrect email or password.");
      } else if (err.response && err.response.data && err.response.data.detail) {
        setError(err.response.data.detail);
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
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-500 text-sm font-bold">SS</div>
          <p className="mt-16 text-sm font-medium text-brand-200">AI-powered complaint intelligence</p>
          <h1 className="mt-3 text-3xl font-bold leading-tight">Resolve issues.<br />Build trust.</h1>
          <p className="mt-5 text-sm leading-6 text-slate-300">One transparent platform for students, officers, administrators, and leadership.</p>
        </div>
        <div className="p-6 sm:p-10">
        <p className="text-sm font-semibold text-brand-600">Welcome back</p>
        <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900">Sign in to Samadhan Setu</h1>
        <p className="mt-2 text-sm text-slate-500">Continue managing complaints and resolutions.</p>

        {successMessage && (
          <p className="mt-4 rounded-xl border border-green-200 bg-green-50 px-3 py-2 text-center text-sm text-green-700">
            {successMessage}
          </p>
        )}

        <div className="mt-6 rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <p className="text-xs font-medium text-slate-600">Demo accounts</p>
          <p className="mt-1 text-xs text-slate-500">
            Select a role, then click Login. Demo password: <strong>password123</strong>
          </p>
          <div className="mt-2 grid grid-cols-2 gap-2">
            {DEMO_ACCOUNTS.map((account) => (
              <button
                key={account.email}
                type="button"
                onClick={() => {
                  setEmail(account.email);
                  setPassword("password123");
                  setError("");
                }}
                className="rounded-xl border border-slate-200 bg-white px-2 py-2 text-xs font-semibold text-slate-700 hover:border-brand-300 hover:bg-brand-50"
              >
                {account.label}
              </button>
            ))}
          </div>
        </div>

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-slate-700">
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-slate-700">
              Password
            </label>
            <input
              id="password"
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
            />
          </div>

          {error && (
            <p className="text-sm text-red-600" role="alert">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={isLoading}
            className="w-full rounded-xl bg-brand-600 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isLoading ? "Logging in..." : "Login"}
          </button>
        </form>

        <p className="mt-4 text-sm text-slate-500 text-center">
          Don't have an account?{" "}
          <Link to="/register" className="text-slate-800 font-medium hover:underline">
            Register
          </Link>
        </p>
        </div>
      </div>
    </div>
  );
}

export default Login;
