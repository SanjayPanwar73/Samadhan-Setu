import { Navigate, Outlet } from "react-router-dom";
import { isAuthenticated, getRole } from "../utils/auth";

/**
 * Route guard used to wrap a group of <Route> elements.
 *
 * Usage:
 *   <Route element={<ProtectedRoute allowedRoles={["staff"]} />}>
 *     <Route path="/staff" element={<StaffDashboard />} />
 *   </Route>
 *
 * - No token at all      -> redirect to /login
 * - Token, wrong role     -> redirect to that user's own dashboard
 * - Token, allowed role   -> render the nested route (<Outlet />)
 *
 * If allowedRoles is omitted, any authenticated user may access
 * the route regardless of role.
 */
function ProtectedRoute({ allowedRoles }) {
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />;
  }

  const role = getRole();

  // Token exists but couldn't be decoded / has no role / is expired.
  if (!role) {
    return <Navigate to="/login" replace />;
  }

  if (allowedRoles && !allowedRoles.includes(role)) {
    return <Navigate to="/unauthorized" replace state={{ from: window.location.pathname }} />;
  }

  return <Outlet />;
}

export default ProtectedRoute;
