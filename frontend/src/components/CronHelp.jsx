const EXAMPLES = [
  { expr: "* * * * *", desc: "Every minute" },
  { expr: "*/5 * * * *", desc: "Every 5 minutes" },
  { expr: "0 * * * *", desc: "Every hour" },
  { expr: "0 6 * * *", desc: "Daily at 6:00 AM (UTC)" },
  { expr: "30 9 * * 1-5", desc: "9:30 AM UTC, Mon–Fri" },
];

export default function CronHelp() {
  return (
    <div className="mt-2 text-xs text-gray-500">
      <p className="mb-1">
        Format: <code className="font-mono">minute hour day month weekday</code>{" "}
        (all times UTC). Examples:
      </p>
      <ul className="space-y-0.5">
        {EXAMPLES.map((e) => (
          <li key={e.expr}>
            <code className="font-mono text-gray-700">{e.expr}</code>
            <span className="text-gray-400"> — {e.desc}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
