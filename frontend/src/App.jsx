import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import ProtectedRoute from "./routes/ProtectedRoute";
import UserLayout from "./components/UserLayout";

import Login from "./pages/Login";
import Register from "./pages/Register";
import Complaints from "./pages/Complaints";
import NewComplaint from "./pages/NewComplaint";
import ComplaintDetail from "./pages/ComplaintDetail";
import Staff from "./pages/Staff";
import Admin from "./pages/Admin";
import Departments from "./pages/Departments";
import Management from "./pages/Management";
import Unauthorized from "./pages/Unauthorized";
import NotFound from "./pages/NotFound";
import Profile from "./pages/Profile";
import Notifications from "./pages/Notifications";
import { getHomeRouteForRole, getRole } from "./utils/auth";

function DashboardRedirect() {
  return <Navigate to={getHomeRouteForRole(getRole())} replace />;
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public routes */}
        <Route path="/" element={<Navigate to="/login" replace />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/unauthorized" element={<Unauthorized />} />

        <Route
          element={
            <ProtectedRoute allowedRoles={["user", "staff", "admin", "management"]} />
          }
        >
          <Route element={<UserLayout />}>
            <Route path="/profile" element={<Profile />} />
            <Route path="/notifications" element={<Notifications />} />
            <Route path="/dashboard" element={<DashboardRedirect />} />
            <Route element={<ProtectedRoute allowedRoles={["user"]} />}>
              <Route path="/complaints" element={<Complaints />} />
              <Route path="/complaints/new" element={<NewComplaint />} />
            </Route>
            <Route element={<ProtectedRoute allowedRoles={["staff"]} />}>
              <Route path="/staff" element={<Staff />} />
            </Route>
            <Route element={<ProtectedRoute allowedRoles={["admin"]} />}>
              <Route path="/admin" element={<Admin />} />
              <Route path="/admin/departments" element={<Departments />} />
            </Route>
            <Route element={<ProtectedRoute allowedRoles={["management"]} />}>
              <Route path="/management" element={<Management />} />
            </Route>
            <Route element={<ProtectedRoute allowedRoles={["user", "staff", "admin", "management"]} />}>
              <Route path="/complaints/:id" element={<ComplaintDetail />} />
            </Route>
          </Route>
        </Route>

        {/* Catch-all */}
        <Route path="*" element={<NotFound />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
