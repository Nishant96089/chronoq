import { Routes, Route, Navigate } from "react-router-dom";
import LoginPage from "./pages/LoginPage";
import JobsPage from "./pages/JobsPage";
import ProtectedRoute from "./components/ProtectedRoute";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/jobs"
        element={
          <ProtectedRoute>
            <JobsPage />
          </ProtectedRoute>
        }
      />
      {/* Default: send to /jobs (which bounces to /login if not authed) */}
      <Route path="/" element={<Navigate to="/jobs" replace />} />
      {/* Catch-all */}
      <Route path="*" element={<Navigate to="/jobs" replace />} />
    </Routes>
  );
}
