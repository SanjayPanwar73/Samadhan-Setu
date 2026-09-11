import { Link, useNavigate } from "react-router-dom";
import { getHomeRouteForRole } from "../utils/auth";
import { useAuth } from "../contexts/AuthContext";
import Brand from "../components/Brand";
import Icon from "../components/Icon";
import { Button } from "../components/ui";
import { useEffect } from "react";
export default function Unauthorized() {
  useEffect(() => {
    document.title = "Access required · Samadhan Setu";
  }, []);
  const { role, signOut } = useAuth();
  const navigate = useNavigate();
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-[#f6f8f7] px-5 text-center">
      <Brand />
      <div className="mt-14 grid h-20 w-20 place-items-center rounded-2xl border border-brand-100 bg-brand-50 text-brand-600">
        <Icon name="shield" size={36} />
      </div>
      <h1 className="mt-7 text-2xl font-semibold tracking-tight text-brand-900">
        This space needs different access.
      </h1>
      <p className="mt-3 max-w-md text-sm leading-6 text-slate-500">
        Your {role || "current"} account doesn’t have permission to view this
        page. You can return to your workspace or sign in with another account.
      </p>
      <div className="mt-7 flex flex-wrap justify-center gap-3">
        <Link to={getHomeRouteForRole(role)} className="btn btn-primary">
          <Icon name="arrowLeft" size={16} />
          Back to workspace
        </Link>
        <Button
          variant="secondary"
          onClick={() => {
            signOut();
            navigate("/login", { replace: true });
          }}
        >
          Switch account
        </Button>
      </div>
    </main>
  );
}
