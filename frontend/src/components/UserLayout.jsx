import { useEffect, useRef, useState } from "react";
import {
  Link,
  NavLink,
  Outlet,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { canonicalRole, getDisplayName, getHomeRouteForRole, roleLabel } from "../utils/auth";
import NotificationBell from "./NotificationBell";
import EnrollmentPrompt from "./EnrollmentPrompt";
import { useAuth } from "../contexts/AuthContext";
import Brand from "./Brand";
import Icon from "./Icon";
import { Alert, Button, Modal } from "./ui";

const TITLES = {
  "/complaints": "My complaints",
  "/complaints/new": "New complaint",
  "/tasks": "My tasks",
  "/department": "Issue queue",
  "/department/staff": "Staff workload",
  "/hod": "Department overview",
  "/super/users": "Users and roles",
  "/super/departments": "Departments",
  "/super/locations-assets": "Locations and assets",
  "/super/config": "Priority and SLA",
  "/super/audit": "Audit trail",
  "/notifications": "Notifications",
  "/profile": "My profile",
};
const WORKSPACE_LABELS = {
  student: "Student workspace",
  staff: "Staff workspace",
  dept_admin: "Department workspace",
  hod: "Head of department",
  super_admin: "Admin workspace",
};

function navigationFor(role) {
  switch (canonicalRole(role)) {
    case "student":
      return [
        { to: "/complaints", icon: "grid", label: "My complaints", end: true },
        { to: "/complaints/new", icon: "plus", label: "New complaint" },
      ];
    case "staff":
      return [{ to: "/tasks", icon: "grid", label: "My tasks", end: true }];
    case "dept_admin":
      return [
        { to: "/department", icon: "grid", label: "Issue queue", end: true },
        { to: "/department/staff", icon: "users", label: "Staff workload" },
      ];
    case "hod":
      return [{ to: "/hod", icon: "chart", label: "Overview", end: true }];
    case "super_admin":
      return [
        { to: "/super/users", icon: "users", label: "Users and roles" },
        { to: "/super/departments", icon: "building", label: "Departments" },
        { to: "/super/locations-assets", icon: "grid", label: "Locations and assets" },
        { to: "/super/config", icon: "sparkles", label: "Priority and SLA" },
        { to: "/super/audit", icon: "shield", label: "Audit trail" },
        { to: "/department", icon: "chart", label: "Issue queue" },
      ];
    default:
      return [];
  }
}

export default function UserLayout() {
  const { user, role, error, refreshUser, signOut } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const [logoutOpen, setLogoutOpen] = useState(false);
  const sidebar = useRef(null);
  const menuButton = useRef(null);
  const home = getHomeRouteForRole(role);
  const title =
    TITLES[location.pathname] ||
    (location.pathname.startsWith("/complaints/")
      ? "Complaint details"
      : location.pathname.startsWith("/tasks/")
        ? "Task details"
        : location.pathname.startsWith("/department/issues/")
          ? "Issue details"
          : "Workspace");
  const name = getDisplayName(user);
  const initials = name
    .split(" ")
    .slice(0, 2)
    .map((part) => part[0])
    .join("");

  useEffect(() => {
    document.title = `${title} · Samadhan Setu`;
    window.scrollTo(0, 0);
  }, [title, location.pathname]);

  useEffect(() => {
    if (!menuOpen) return;
    const container = sidebar.current;
    const trigger = menuButton.current;
    const original = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    container.querySelector("a,button")?.focus();
    function onKey(event) {
      if (event.key === "Escape") setMenuOpen(false);
      if (event.key !== "Tab") return;
      const items = [
        ...container.querySelectorAll("a,button:not(:disabled)"),
      ].filter((item) => item.getClientRects().length);
      const first = items[0],
        last = items.at(-1);
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      }
      if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    }
    function onResize() {
      if (window.innerWidth >= 768) setMenuOpen(false);
    }
    document.addEventListener("keydown", onKey);
    window.addEventListener("resize", onResize);
    return () => {
      document.body.style.overflow = original;
      document.removeEventListener("keydown", onKey);
      window.removeEventListener("resize", onResize);
      trigger?.focus();
    };
  }, [menuOpen]);

  const navigation = navigationFor(role);
  const isStudent = canonicalRole(role) === "student";
  return (
    <div className="app-shell">
      <a href="#main-content" className="skip-link">
        Skip to content
      </a>
      {menuOpen && (
        <div
          className="sidebar-overlay"
          onClick={() => setMenuOpen(false)}
          aria-hidden="true"
        />
      )}
      <aside
        ref={sidebar}
        id="workspace-navigation"
        className={`sidebar ${menuOpen ? "is-open" : ""}`}
        role={menuOpen ? "dialog" : undefined}
        aria-modal={menuOpen || undefined}
        aria-label="Workspace navigation"
      >
        <div className="relative">
          <Link
            to={home}
            onClick={() => setMenuOpen(false)}
            className="sidebar-brand block"
          >
            <Brand />
          </Link>
          {menuOpen && (
            <Button
              variant="ghost"
              className="icon-button absolute right-1 top-1 md:hidden"
              aria-label="Close navigation"
              onClick={() => setMenuOpen(false)}
            >
              <Icon name="x" size={16} />
            </Button>
          )}
        </div>
        <div className="workspace-label">
          <div className="flex items-center gap-2.5">
            <span className="workspace-icon">
              <Icon name="building" size={16} />
            </span>
            <span>{WORKSPACE_LABELS[canonicalRole(role)] || "Workspace"}</span>
          </div>
          <Icon name="shield" size={14} />
        </div>
        <p className="nav-section-label">Workspace</p>
        <nav
          aria-label="Primary"
          className="sidebar-nav"
          onClick={() => setMenuOpen(false)}
        >
          {navigation.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `sidebar-link ${isActive ? "active" : ""}`
              }
            >
              <Icon name={item.icon} size={18} />
              {item.label}
            </NavLink>
          ))}
          <NavLink
            to="/notifications"
            className={({ isActive }) =>
              `sidebar-link ${isActive ? "active" : ""}`
            }
          >
            <Icon name="bell" size={18} />
            Notifications
          </NavLink>
        </nav>
        <p className="nav-section-label mt-8">Account</p>
        <nav
          aria-label="Account"
          className="sidebar-nav"
          onClick={() => setMenuOpen(false)}
        >
          <NavLink
            to="/profile"
            className={({ isActive }) =>
              `sidebar-link ${isActive ? "active" : ""}`
            }
          >
            <Icon name="user" size={18} />
            My profile
          </NavLink>
        </nav>
        <div className="min-h-8" />
        <div className="sidebar-help">
          <Icon name="sparkles" size={19} className="text-brand-500" />
          <h3>Small steps. Better outcomes.</h3>
          <p>
            {isStudent
              ? "A clear description helps your concern reach the right team."
              : "Keep your workspace moving. Every resolution makes a difference."}
          </p>
          {isStudent && (
            <Link
              to="/complaints/new"
              onClick={() => setMenuOpen(false)}
              className="mt-3 inline-flex items-center gap-2 text-xs font-semibold text-brand-700"
            >
              Raise a concern <Icon name="arrowRight" size={13} />
            </Link>
          )}
        </div>
        <div className="sidebar-footer">
          <Link
            to="/profile"
            onClick={() => setMenuOpen(false)}
            className="avatar"
            aria-label="Open your profile"
          >
            {initials}
          </Link>
          <div className="min-w-0 flex-1">
            <p className="truncate text-xs font-semibold text-slate-700">
              {name}
            </p>
            <p className="mt-1 text-[10px] capitalize text-slate-500">
              {roleLabel(role)}
            </p>
          </div>
          <Button
            variant="ghost"
            className="icon-button"
            aria-label="Sign out"
            onClick={() => {
              setMenuOpen(false);
              setLogoutOpen(true);
            }}
          >
            <Icon name="logout" size={17} />
          </Button>
        </div>
      </aside>
      <div className="workspace-body" inert={menuOpen || undefined}>
        <header className="topbar">
          <div className="flex min-w-0 items-center gap-2">
            <button
              ref={menuButton}
              className="btn btn-ghost icon-button mobile-menu-button"
              aria-label="Open navigation"
              aria-expanded={menuOpen}
              aria-controls="workspace-navigation"
              onClick={() => setMenuOpen(true)}
            >
              <Icon name="menu" />
            </button>
            <div className="breadcrumb">
              <Link to={home} className="hidden sm:inline">
                Workspace
              </Link>
              <Icon name="chevronRight" size={12} className="hidden sm:block" />
              <strong>{title}</strong>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className="hidden text-[11px] text-slate-500 lg:block">
              {new Date().toLocaleDateString(undefined, {
                weekday: "short",
                month: "short",
                day: "numeric",
              })}
            </span>
            <NotificationBell />
            <span className="h-6 w-px bg-slate-200" />
            <Link to="/profile" className="avatar" aria-label="Open profile">
              {initials}
            </Link>
          </div>
        </header>
        <main id="main-content" tabIndex={-1} className="workspace-main">
          {error && location.pathname !== "/profile" && (
            <Alert variant="error" className="mb-5">
              {error}{" "}
              <button
                type="button"
                className="underline font-semibold"
                onClick={() => refreshUser({ force: true })}
              >
                Retry profile
              </button>
            </Alert>
          )}
          {user?.needs_enrollment_no && (
            <EnrollmentPrompt onDone={() => refreshUser({ force: true })} />
          )}
          <Outlet />
        </main>
        <footer className="mx-4 flex flex-wrap justify-between gap-2 border-t border-slate-200/70 px-1 py-5 text-[10px] text-slate-500 sm:mx-8">
          <span>Samadhan Setu · A better way forward</span>
          <span>Clarity in every concern.</span>
        </footer>
      </div>
      <Modal
        open={logoutOpen}
        onClose={() => setLogoutOpen(false)}
        title="Sign out of your workspace?"
        description="You can sign back in at any time to continue where you left off."
        footer={
          <>
            <Button variant="secondary" onClick={() => setLogoutOpen(false)}>
              Stay signed in
            </Button>
            <Button
              onClick={() => {
                signOut();
                navigate("/login", { replace: true });
              }}
            >
              Sign out
            </Button>
          </>
        }
      >
        <p className="text-sm text-slate-500">
          Make sure any changes you are working on have been submitted.
        </p>
      </Modal>
    </div>
  );
}
