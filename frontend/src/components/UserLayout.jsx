import { useEffect, useRef, useState } from "react";
import {
  Link,
  NavLink,
  Outlet,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { getDisplayName, getHomeRouteForRole } from "../utils/auth";
import { useAuth } from "../contexts/AuthContext";
import Brand from "./Brand";
import Icon from "./Icon";
import { Alert, Button, Modal } from "./ui";

const TITLES = {
  "/complaints": "Overview",
  "/complaints/new": "New complaint",
  "/staff": "Assigned to me",
  "/admin": "Administration",
  "/admin/departments": "Departments",
  "/management": "Analytics",
  "/notifications": "Activity",
  "/profile": "My profile",
};
const ROLE_LABELS = {
  user: "Personal workspace",
  staff: "Staff workspace",
  admin: "Admin workspace",
  management: "Management workspace",
};

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

  const navigation = [
    {
      to: home,
      icon: "grid",
      label: role === "staff" ? "Assigned to me" : "Overview",
      end: true,
    },
  ];
  if (role === "user")
    navigation.push({
      to: "/complaints/new",
      icon: "plus",
      label: "New complaint",
    });
  if (role === "admin")
    navigation.push(
      { to: "/admin/departments", icon: "building", label: "Departments" },
      { to: "/management", icon: "chart", label: "Analytics" },
    );
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
            <span>{ROLE_LABELS[role] || "Workspace"}</span>
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
            Activity
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
            {role === "user"
              ? "A clear description helps your concern reach the right team."
              : "Keep your workspace moving. Every resolution makes a difference."}
          </p>
          {role === "user" && (
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
              {role} account
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
            <Link
              to="/notifications"
              className="btn btn-ghost icon-button"
              aria-label="View activity"
            >
              <Icon name="bell" size={19} />
            </Link>
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
