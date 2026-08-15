const STYLES = {
  success: "bg-green-100 text-green-800 border-green-200",
  failed: "bg-red-100 text-red-800 border-red-200",
  pending: "bg-gray-100 text-gray-700 border-gray-200",
  running: "bg-blue-100 text-blue-800 border-blue-200",
  timeout: "bg-amber-100 text-amber-800 border-amber-200",
};

export default function StatusBadge({ status }) {
  const cls = STYLES[status] || STYLES.pending;
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs
                  font-medium border ${cls}`}
    >
      {status}
    </span>
  );
}
