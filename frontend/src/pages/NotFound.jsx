import { Link } from "react-router-dom";
import { getHomeRouteForRole, getRole } from "../utils/auth";
import Brand from "../components/Brand";
import Icon from "../components/Icon";
import { useEffect } from "react";

export default function NotFound() {
  useEffect(() => {
    document.title = "Page not found · Samadhan Setu";
  }, []);
  const role = getRole();
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-[#f6f8f7] px-5 text-center">
      <Brand />
      <p className="mt-14 text-8xl font-semibold tracking-tighter text-brand-200">
        404
      </p>
      <h1 className="mt-6 text-2xl font-semibold tracking-tight text-brand-900">
        This page has taken a different path.
      </h1>
      <p className="mt-3 max-w-md text-sm leading-6 text-slate-500">
        The link may have changed, or the page may no longer exist. Let’s get
        you back to your workspace.
      </p>
      <Link to={getHomeRouteForRole(role)} className="btn btn-primary mt-7">
        <Icon name="arrowLeft" size={16} />
        {role ? "Back to workspace" : "Go to sign in"}
      </Link>
    </main>
  );
}
