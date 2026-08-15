import { Link } from "react-router-dom";
import { useJobs } from "../hooks/useJobs";
import Layout from "../components/Layout";

function formatDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
}

export default function JobsPage() {
  const { data, isLoading, isError, error } = useJobs();

  return (
    <Layout>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Jobs</h2>
          <p className="text-sm text-gray-500 mt-1">
            Scheduled HTTP jobs and their next run.
          </p>
        </div>
        <Link
          to="/jobs/new"
          className="bg-indigo-600 text-white text-sm font-medium px-4 py-2
                     rounded-lg hover:bg-indigo-700 transition"
        >
          + New job
        </Link>
      </div>

      {isLoading && (
        <div className="text-gray-500 text-sm py-12 text-center">
          Loading jobs…
        </div>
      )}

      {isError && (
        <div className="text-red-600 bg-red-50 border border-red-200 rounded-lg
                        px-4 py-3 text-sm">
          Failed to load jobs: {error?.message || "unknown error"}
        </div>
      )}

      {data && data.results.length === 0 && (
        <div className="text-center py-16 bg-white rounded-xl border
                        border-gray-200">
          <p className="text-gray-600">No jobs yet.</p>
          <Link
            to="/jobs/new"
            className="inline-block mt-3 text-indigo-600 hover:text-indigo-700
                       font-medium text-sm"
          >
            Create your first job →
          </Link>
        </div>
      )}

      {data && data.results.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr className="text-left text-gray-500">
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Schedule</th>
                <th className="px-4 py-3 font-medium">Method</th>
                <th className="px-4 py-3 font-medium">Next run</th>
                <th className="px-4 py-3 font-medium">Active</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {data.results.map((job) => (
                <tr key={job.public_id} className="hover:bg-gray-50 transition">
                  <td className="px-4 py-3">
                    <Link
                      to={`/jobs/${job.public_id}`}
                      className="font-medium text-indigo-600 hover:text-indigo-700"
                    >
                      {job.name}
                    </Link>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-gray-600">
                    {job.schedule_cron}
                  </td>
                  <td className="px-4 py-3 text-gray-700">{job.http_method}</td>
                  <td className="px-4 py-3 text-gray-600">
                    {formatDate(job.next_fire_at)}
                  </td>
                  <td className="px-4 py-3">
                    {job.is_active ? (
                      <span className="text-green-600 font-medium">Yes</span>
                    ) : (
                      <span className="text-gray-400">No</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Layout>
  );
}
