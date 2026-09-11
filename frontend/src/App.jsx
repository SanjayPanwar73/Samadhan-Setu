import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import ProtectedRoute from "./routes/ProtectedRoute";
import UserLayout from "./components/UserLayout";
import ErrorBoundary from "./components/ErrorBoundary";
import { AuthProvider, useAuth } from "./contexts/AuthContext";
import { PageSkeleton } from "./components/ui";
import { getHomeRouteForRole } from "./utils/auth";

const Login = lazy(() => import("./pages/Login"));
const Register = lazy(() => import("./pages/Register"));
const Complaints = lazy(() => import("./pages/Complaints"));
const NewComplaint = lazy(() => import("./pages/NewComplaint"));
const ComplaintDetail = lazy(() => import("./pages/ComplaintDetail"));
const Staff = lazy(() => import("./pages/Staff"));
const Admin = lazy(() => import("./pages/Admin"));
const Departments = lazy(() => import("./pages/Departments"));
const Management = lazy(() => import("./pages/Management"));
const Unauthorized = lazy(() => import("./pages/Unauthorized"));
const NotFound = lazy(() => import("./pages/NotFound"));
const Profile = lazy(() => import("./pages/Profile"));
const Notifications = lazy(() => import("./pages/Notifications"));

function DashboardRedirect() {
  const { role } = useAuth();
  return <Navigate to={getHomeRouteForRole(role)} replace />;
}
function Page({ children }) {
  return <Suspense fallback={<PageSkeleton />}>{children}</Suspense>;
}

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <AuthProvider>
          <Suspense
            fallback={
              <div className="mx-auto max-w-6xl p-8">
                <PageSkeleton />
              </div>
            }
          >
            <Routes>
              <Route path="/" element={<DashboardRedirect />} />
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route path="/unauthorized" element={<Unauthorized />} />
              <Route
                element={
                  <ProtectedRoute
                    allowedRoles={["user", "staff", "admin", "management"]}
                  />
                }
              >
                <Route element={<UserLayout />}>
                  <Route
                    path="/profile"
                    element={
                      <Page>
                        <Profile />
                      </Page>
                    }
                  />
                  <Route
                    path="/notifications"
                    element={
                      <Page>
                        <Notifications />
                      </Page>
                    }
                  />
                  <Route path="/dashboard" element={<DashboardRedirect />} />
                  <Route element={<ProtectedRoute allowedRoles={["user"]} />}>
                    <Route
                      path="/complaints"
                      element={
                        <Page>
                          <Complaints />
                        </Page>
                      }
                    />
                    <Route
                      path="/complaints/new"
                      element={
                        <Page>
                          <NewComplaint />
                        </Page>
                      }
                    />
                  </Route>
                  <Route element={<ProtectedRoute allowedRoles={["staff"]} />}>
                    <Route
                      path="/staff"
                      element={
                        <Page>
                          <Staff />
                        </Page>
                      }
                    />
                  </Route>
                  <Route element={<ProtectedRoute allowedRoles={["admin"]} />}>
                    <Route
                      path="/admin"
                      element={
                        <Page>
                          <Admin />
                        </Page>
                      }
                    />
                    <Route
                      path="/admin/departments"
                      element={
                        <Page>
                          <Departments />
                        </Page>
                      }
                    />
                  </Route>
                  <Route
                    element={
                      <ProtectedRoute allowedRoles={["management", "admin"]} />
                    }
                  >
                    <Route
                      path="/management"
                      element={
                        <Page>
                          <Management />
                        </Page>
                      }
                    />
                  </Route>
                  <Route
                    path="/complaints/:id"
                    element={
                      <Page>
                        <ComplaintDetail />
                      </Page>
                    }
                  />
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
