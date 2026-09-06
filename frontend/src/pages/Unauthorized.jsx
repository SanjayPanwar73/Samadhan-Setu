import { Link } from "react-router-dom";
import { getHomeRouteForRole, getRole, logout } from "../utils/auth";

function Unauthorized() {
  const role = getRole();
  const homeRoute = getHomeRouteForRole(role);

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-md rounded-lg bg-white p-8 text-center shadow">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-red-100 text-xl text-red-700">
          !
        </div>
        <h1 className="mt-4 text-2xl font-semibold text-slate-800">Access denied</h1>
        <p className="mt-2 text-sm text-slate-500">
          Your {role || "current"} account does not have permission to view this page.
        </p>
        <div className="mt-6 flex justify-center gap-3">
          <Link to={homeRoute} className="rounded-md bg-slate-800 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700">
            Go to dashboard
          </Link>
          <button
            onClick={() => {
              logout();
              window.location.href = "/login";
            }}
            className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Log out
          </button>
        </div>
      </div>
    </div>
  );
}

export default Unauthorized;
