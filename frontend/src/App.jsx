import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import ProtectedRoute from "./routes/ProtectedRoute";
import UserLayout from "./components/UserLayout";
import ErrorBoundary from "./components/ErrorBoundary";
import { AuthProvider, useAuth } from "./contexts/AuthContext";
import { PageSkeleton } from "./components/ui";
import { canonicalRole, getHomeRouteForRole } from "./utils/auth";

const Login = lazy(() => import("./pages/Login"));
const Register = lazy(() => import("./pages/Register"));
const Unauthorized = lazy(() => import("./pages/Unauthorized"));
const NotFound = lazy(() => import("./pages/NotFound"));
const Profile = lazy(() => import("./pages/Profile"));
const Notifications = lazy(() => import("./pages/Notifications"));
// student
const Complaints = lazy(() => import("./pages/Complaints"));
const NewComplaint = lazy(() => import("./pages/NewComplaint"));
const ComplaintDetail = lazy(() => import("./pages/ComplaintDetail"));
// staff
const Tasks = lazy(() => import("./pages/Tasks"));
const TaskDetail = lazy(() => import("./pages/TaskDetail"));
// department admin
const Department = lazy(() => import("./pages/Department"));
const IssueDetail = lazy(() => import("./pages/IssueDetail"));
const DepartmentStaff = lazy(() => import("./pages/DepartmentStaff"));
// head of department
const Hod = lazy(() => import("./pages/Hod"));
// super admin
const SuperUsers = lazy(() => import("./pages/SuperUsers"));
const SuperDepartments = lazy(() => import("./pages/SuperDepartments"));
const SuperLocationsAssets = lazy(() => import("./pages/SuperLocationsAssets"));
const SuperConfig = lazy(() => import("./pages/SuperConfig"));
const SuperAudit = lazy(() => import("./pages/SuperAudit"));

const ALL_ROLES = ["student", "staff", "dept_admin", "hod", "super_admin"];

function DashboardRedirect() {
  const { role } = useAuth();
  return <Navigate to={getHomeRouteForRole(role)} replace />;
}
function ManagementRedirect() {
  const { role } = useAuth();
  return <Navigate to={canonicalRole(role) === "super_admin" ? "/department" : "/hod"} replace />;
}
function Page({ children }) {
  return <Suspense fallback={<PageSkeleton />}>{children}</Suspense>;
}

/** [path, Component, allowed roles]. Each group is wrapped in its own role guard. */
export const ROUTES = [
  ["/profile", Profile, ALL_ROLES],
  ["/notifications", Notifications, ALL_ROLES],
  ["/complaints", Complaints, ["student"]],
  ["/complaints/new", NewComplaint, ["student"]],
  ["/complaints/:id", ComplaintDetail, ["student"]],
  ["/tasks", Tasks, ["staff"]],
  ["/tasks/:id", TaskDetail, ["staff"]],
  ["/department", Department, ["dept_admin", "super_admin"]],
  ["/department/staff", DepartmentStaff, ["dept_admin", "super_admin", "hod"]],
  ["/department/issues/:id", IssueDetail, ["dept_admin", "super_admin"]],
  ["/hod", Hod, ["hod"]],
  ["/super/users", SuperUsers, ["super_admin"]],
  ["/super/departments", SuperDepartments, ["super_admin"]],
  ["/super/locations-assets", SuperLocationsAssets, ["super_admin"]],
  ["/super/config", SuperConfig, ["super_admin"]],
  ["/super/audit", SuperAudit, ["super_admin"]],
];

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <AuthProvider>
          <Suspense fallback={<div className="mx-auto max-w-6xl p-8"><PageSkeleton /></div>}>
            <Routes>
              <Route path="/" element={<DashboardRedirect />} />
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route path="/unauthorized" element={<Unauthorized />} />
              <Route element={<ProtectedRoute allowedRoles={ALL_ROLES} />}>
                <Route element={<UserLayout />}>
                  <Route path="/dashboard" element={<DashboardRedirect />} />
                  {/* The V1 /management, /admin and /staff URLs redirect to their V2 homes. */}
                  <Route path="/management" element={<ManagementRedirect />} />
                  <Route path="/admin" element={<Navigate to="/super/users" replace />} />
                  <Route path="/staff" element={<Navigate to="/tasks" replace />} />
                  {ROUTES.map(([path, Component, roles]) => (
                    <Route key={path} element={<ProtectedRoute allowedRoles={roles} />}>
                      <Route path={path} element={<Page><Component /></Page>} />
                    </Route>
                  ))}
                </Route>
              </Route>
              <Route path="*" element={<NotFound />} />
            </Routes>
          </Suspense>
        </AuthProvider>
      </BrowserRouter>
    </ErrorBoundary>
  );
}
