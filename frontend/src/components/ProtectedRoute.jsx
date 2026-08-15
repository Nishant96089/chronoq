import { Navigate } from "react-router-dom";
import { isAuthenticated } from "../api/auth";

// Wraps a page. If not logged in, redirect to /login.
export default function ProtectedRoute({ children }) {
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />;
  }
  return children;
}
