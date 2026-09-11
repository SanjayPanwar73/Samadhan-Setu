import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { isAuthenticated } from "../utils/auth";
import { Button, ErrorState, PageSkeleton } from "../components/ui";

function ProtectedRoute({ allowedRoles }) {
  const location = useLocation();
  const { user, role, loading, error, refreshUser, signOut } = useAuth();
  const from = `${location.pathname}${location.search}${location.hash}`;

  if (!isAuthenticated())
    return <Navigate to="/login" replace state={{ from }} />;
  if (loading && !user)
    return (
      <div className="mx-auto max-w-7xl p-6 sm:p-10">
        <PageSkeleton />
      </div>
    );
  if (error && !user) {
    return (
      <div className="mx-auto max-w-xl p-6 pt-20">
        <ErrorState message={error} onRetry={() => refreshUser()} />
        <div className="mt-4 text-center">
          <Button variant="ghost" onClick={signOut}>
            Return to sign in
          </Button>
        </div>
      </div>
    );
  }
  if (allowedRoles && !allowedRoles.includes(role))
    return <Navigate to="/unauthorized" replace state={{ from }} />;
  return <Outlet />;
}

export default ProtectedRoute;
