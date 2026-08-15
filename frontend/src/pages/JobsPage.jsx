import { logout } from "../api/auth";
import { useNavigate } from "react-router-dom";

export default function JobsPage() {
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate("/login");
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-5xl mx-auto px-4 py-4 flex items-center justify-between">
          <h1 className="text-xl font-bold text-gray-900">chronoq</h1>
          <button
            onClick={handleLogout}
            className="text-sm text-gray-600 hover:text-gray-900"
          >
            Sign out
          </button>
        </div>
      </header>
      <main className="max-w-5xl mx-auto px-4 py-8">
        <p className="text-gray-700">
          You're logged in. Jobs list coming in step 4.4.
        </p>
      </main>
    </div>
  );
}
