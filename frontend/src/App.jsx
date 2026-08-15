import { Routes, Route, Navigate } from "react-router-dom";
import LoginPage from "./pages/LoginPage";
import JobsPage from "./pages/JobsPage";
import CreateJobPage from "./pages/CreateJobPage";
import JobDetailPage from "./pages/JobDetailPage";
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
      {/* Static /jobs/new must be declared before the dynamic :publicId
          so it's never swallowed by the param route. */}
      <Route
        path="/jobs/new"
        element={
          <ProtectedRoute>
            <CreateJobPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/jobs/:publicId"
        element={
          <ProtectedRoute>
            <JobDetailPage />
          </ProtectedRoute>
        }
      />

      <Route path="/" element={<Navigate to="/jobs" replace />} />
      <Route path="*" element={<Navigate to="/jobs" replace />} />
    </Routes>
  );
}
