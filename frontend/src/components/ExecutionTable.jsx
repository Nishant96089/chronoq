import StatusBadge from "./StatusBadge";
import { formatDateTime, timeAgo, durationMs } from "../utils/time";

export default function ExecutionTable({ executions, isRefetching }) {
  if (!executions || executions.length === 0) {
    return (
      <div className="text-center py-12 bg-white rounded-xl border border-gray-200">
        <p className="text-gray-500 text-sm">
          No executions yet. They'll appear here as the job fires.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
      <div className="px-4 py-2 border-b border-gray-100 flex items-center
                      justify-between">
        <span className="text-xs text-gray-400">
          {isRefetching ? "Refreshing…" : "Auto-refreshing every 5s"}
        </span>
      </div>
      <table className="w-full text-sm">
        <thead className="bg-gray-50 border-b border-gray-200">
          <tr className="text-left text-gray-500">
            <th className="px-4 py-2 font-medium">Status</th>
            <th className="px-4 py-2 font-medium">Scheduled</th>
            <th className="px-4 py-2 font-medium">HTTP</th>
            <th className="px-4 py-2 font-medium">Duration</th>
            <th className="px-4 py-2 font-medium">Attempt</th>
            <th className="px-4 py-2 font-medium">When</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {executions.map((ex) => {
            const dur = durationMs(ex.started_at, ex.finished_at);
            return (
              <tr key={ex.public_id} className="hover:bg-gray-50">
                <td className="px-4 py-2">
                  <StatusBadge status={ex.status} />
                </td>
                <td className="px-4 py-2 text-gray-600 font-mono text-xs">
                  {formatDateTime(ex.scheduled_for)}
                </td>
                <td className="px-4 py-2 text-gray-700">
                  {ex.http_status_code ?? "—"}
                </td>
                <td className="px-4 py-2 text-gray-600">
                  {dur !== null ? `${dur} ms` : "—"}
                </td>
                <td className="px-4 py-2 text-gray-600">{ex.attempt_number}</td>
                <td className="px-4 py-2 text-gray-500">
                  {timeAgo(ex.scheduled_for)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
