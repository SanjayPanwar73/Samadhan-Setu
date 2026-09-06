import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { getDisplayName, getHomeRouteForRole, getRole, logout } from "../utils/auth";

const navLinkClasses = ({ isActive }) =>
  `group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors ${
    isActive
      ? "bg-brand-50 text-brand-700 shadow-sm"
      : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
  }`;

function UserLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const role = getRole();
  const homeRoute = getHomeRouteForRole(role);
  const pageTitle = location.pathname === "/profile"
    ? "Profile"
    : location.pathname === "/notifications"
      ? "Notifications"
      : location.pathname.includes("/new")
        ? "New Complaint"
        : role === "staff"
          ? "Staff Dashboard"
          : role === "admin"
            ? "Admin Dashboard"
            : role === "management"
              ? "Management Dashboard"
              : "My Complaints";
  const displayName = getDisplayName({ email: `${role || "user"}@samadhan-setu` });

  function handleLogout() {
    logout();
    navigate("/login", { replace: true });
  }

  return (
    <div className="min-h-screen bg-[#f5f7fb] md:flex">
      <aside className="border-b border-slate-200 bg-white md:flex md:min-h-screen md:w-72 md:flex-col md:border-b-0 md:border-r">
        <div className="flex items-center gap-3 border-b border-slate-100 px-5 py-5">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-600 text-sm font-bold text-white shadow-sm">
            SS
          </div>
          <div>
            <h1 className="text-base font-bold tracking-tight text-slate-900">Samadhan Setu</h1>
            <p className="mt-0.5 text-[11px] font-medium uppercase tracking-wider text-slate-400">
              Complaint intelligence
            </p>
          </div>
        </div>

        <nav aria-label="Primary navigation" className="flex gap-1 overflow-x-auto px-3 py-4 md:block md:flex-1 md:space-y-1">
          <NavLink to={homeRoute} end className={navLinkClasses}>
            <span aria-hidden="true">▦</span><span>Dashboard</span>
          </NavLink>
          {role === "user" && (
            <NavLink to="/complaints/new" className={navLinkClasses}>
              <span aria-hidden="true">＋</span><span>New Complaint</span>
            </NavLink>
          )}
          {role === "admin" && (
            <NavLink to="/admin/departments" className={navLinkClasses}>
              <span aria-hidden="true">⌘</span><span>Departments</span>
            </NavLink>
          )}
          <NavLink to="/notifications" className={navLinkClasses}>
            <span aria-hidden="true">◌</span><span>Notifications</span>
          </NavLink>
          <NavLink to="/profile" className={navLinkClasses}>
            <span aria-hidden="true">◉</span><span>Profile</span>
          </NavLink>
          <button
            onClick={handleLogout}
            className="whitespace-nowrap rounded-xl px-3 py-2.5 text-left text-sm font-semibold text-red-600 hover:bg-red-50 md:hidden"
          >
            ↪ Logout
          </button>
        </nav>

        <div className="hidden border-t border-slate-100 p-4 md:block">
          <div className="mb-3 rounded-xl bg-slate-50 p-3">
            <p className="text-xs font-semibold text-slate-700">{displayName}</p>
            <p className="mt-0.5 text-xs capitalize text-slate-400">{role || "user"} account</p>
          </div>
          <button
            onClick={handleLogout}
            className="w-full rounded-xl px-3 py-2.5 text-left text-sm font-semibold text-red-600 hover:bg-red-50"
          >
            ↪&nbsp; Logout
          </button>
        </div>
      </aside>

      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-200 bg-white/95 px-4 py-3 backdrop-blur sm:px-6">
          <div>
            <p className="text-xs font-medium uppercase tracking-wider text-slate-400">Workspace</p>
            <h2 className="text-lg font-bold text-slate-900">{pageTitle}</h2>
          </div>
          <div className="flex items-center gap-3">
            <NavLink to="/notifications" aria-label="Notifications" className="rounded-xl border border-slate-200 px-3 py-2 text-slate-500 hover:bg-slate-50">◌</NavLink>
            <div className="hidden text-right sm:block">
              <p className="text-sm font-semibold capitalize text-slate-800">{role || "User"}</p>
              <p className="text-xs text-slate-400">Samadhan Setu</p>
            </div>
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-100 text-sm font-bold uppercase text-brand-700">
              {(role || "u").charAt(0)}
            </div>
          </div>
        </header>
        <main className="min-w-0 overflow-x-hidden p-4 sm:p-6 lg:p-8">
          {location.pathname !== homeRoute && (
            <button onClick={() => navigate(homeRoute)} className="mb-5 text-xs font-semibold text-slate-400 hover:text-brand-600">
              ← Back to dashboard
            </button>
          )}
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export default UserLayout;
