import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useCreateJob } from "../hooks/useJobs";
import Layout from "../components/Layout";
import Field from "../components/Field";
import CronHelp from "../components/CronHelp";

const HTTP_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE"];

const inputClass =
  "w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none " +
  "focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-sm";

export default function CreateJobPage() {
  const navigate = useNavigate();
  const createJob = useCreateJob();

  const [form, setForm] = useState({
    name: "",
    target_url: "",
    http_method: "POST",
    schedule_cron: "*/5 * * * *",
    headers: "{}",
    body: "",
    timeout_seconds: 30,
    max_retries: 3,
    retry_backoff_seconds: 60,
    is_active: true,
  });

  // Field-level errors from the backend (e.g. { schedule_cron: ["Invalid..."] }).
  const [fieldErrors, setFieldErrors] = useState({});
  const [formError, setFormError] = useState("");

  function update(key, value) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setFieldErrors({});
    setFormError("");

    // Parse headers JSON client-side so we give a friendly error before hitting the API.
    let parsedHeaders;
    try {
      parsedHeaders = JSON.parse(form.headers || "{}");
    } catch {
      setFieldErrors({ headers: "Headers must be valid JSON, e.g. {\"Key\": \"Value\"}" });
      return;
    }

    const payload = {
      name: form.name,
      target_url: form.target_url,
      http_method: form.http_method,
      schedule_cron: form.schedule_cron,
      headers: parsedHeaders,
      body: form.body,
      timeout_seconds: Number(form.timeout_seconds),
      max_retries: Number(form.max_retries),
      retry_backoff_seconds: Number(form.retry_backoff_seconds),
      is_active: form.is_active,
    };

    try {
      const created = await createJob.mutateAsync(payload);
      navigate(`/jobs/${created.public_id}`);
    } catch (err) {
      const data = err.response?.data;
      if (data && typeof data === "object") {
        // DRF returns { field: ["error", ...], ... }
        const errs = {};
        for (const [k, v] of Object.entries(data)) {
          errs[k] = Array.isArray(v) ? v.join(" ") : String(v);
        }
        setFieldErrors(errs);
        if (data.detail) setFormError(String(data.detail));
      } else {
        setFormError("Failed to create job. Please try again.");
      }
    }
  }

  return (
    <Layout>
      <div className="mb-6">
        <button
          onClick={() => navigate("/jobs")}
          className="text-sm text-gray-500 hover:text-gray-700 mb-2"
        >
          ← Back to jobs
        </button>
        <h2 className="text-2xl font-bold text-gray-900">New job</h2>
      </div>

      <form
        onSubmit={handleSubmit}
        className="bg-white rounded-xl border border-gray-200 p-6 space-y-5
                   max-w-2xl"
      >
        <Field label="Name" error={fieldErrors.name}>
          <input
            className={inputClass}
            value={form.name}
            onChange={(e) => update("name", e.target.value)}
            placeholder="Daily report ping"
            required
          />
        </Field>

        <Field label="Target URL" error={fieldErrors.target_url}>
          <input
            className={inputClass}
            value={form.target_url}
            onChange={(e) => update("target_url", e.target.value)}
            placeholder="https://example.com/webhook"
            type="url"
            required
          />
        </Field>

        <div className="grid grid-cols-2 gap-4">
          <Field label="HTTP method" error={fieldErrors.http_method}>
            <select
              className={inputClass}
              value={form.http_method}
              onChange={(e) => update("http_method", e.target.value)}
            >
              {HTTP_METHODS.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </Field>

          <Field
            label="Timeout (seconds)"
            error={fieldErrors.timeout_seconds}
          >
            <input
              className={inputClass}
              type="number"
              min="1"
              value={form.timeout_seconds}
              onChange={(e) => update("timeout_seconds", e.target.value)}
            />
          </Field>
        </div>

        <Field label="Schedule (cron)" error={fieldErrors.schedule_cron}>
          <input
            className={`${inputClass} font-mono`}
            value={form.schedule_cron}
            onChange={(e) => update("schedule_cron", e.target.value)}
            placeholder="*/5 * * * *"
            required
          />
          <CronHelp />
        </Field>

        <Field
          label="Headers (JSON)"
          error={fieldErrors.headers}
          hint='Optional. Example: {"Authorization": "Bearer xyz"}'
        >
          <textarea
            className={`${inputClass} font-mono`}
            rows={2}
            value={form.headers}
            onChange={(e) => update("headers", e.target.value)}
          />
        </Field>

        <Field label="Body" error={fieldErrors.body} hint="Optional request body.">
          <textarea
            className={inputClass}
            rows={2}
            value={form.body}
            onChange={(e) => update("body", e.target.value)}
            placeholder="(empty)"
          />
        </Field>

        <div className="grid grid-cols-2 gap-4">
          <Field label="Max retries" error={fieldErrors.max_retries}>
            <input
              className={inputClass}
              type="number"
              min="0"
              value={form.max_retries}
              onChange={(e) => update("max_retries", e.target.value)}
            />
          </Field>
          <Field
            label="Retry backoff (seconds)"
            error={fieldErrors.retry_backoff_seconds}
          >
            <input
              className={inputClass}
              type="number"
              min="0"
              value={form.retry_backoff_seconds}
              onChange={(e) => update("retry_backoff_seconds", e.target.value)}
            />
          </Field>
        </div>

        <label className="flex items-center gap-2 text-sm text-gray-700">
          <input
            type="checkbox"
            checked={form.is_active}
            onChange={(e) => update("is_active", e.target.checked)}
            className="rounded border-gray-300"
          />
          Active (start firing immediately)
        </label>

        {formError && (
          <div className="text-sm text-red-600 bg-red-50 border border-red-200
                          rounded-lg px-3 py-2">
            {formError}
          </div>
        )}

        <div className="flex gap-3 pt-2">
          <button
            type="submit"
            disabled={createJob.isPending}
            className="bg-indigo-600 text-white text-sm font-medium px-5 py-2
                       rounded-lg hover:bg-indigo-700 disabled:opacity-50
                       disabled:cursor-not-allowed transition"
          >
            {createJob.isPending ? "Creating…" : "Create job"}
          </button>
          <button
            type="button"
            onClick={() => navigate("/jobs")}
            className="text-sm text-gray-600 px-5 py-2 rounded-lg
                       hover:bg-gray-100 transition"
          >
            Cancel
          </button>
        </div>
      </form>
    </Layout>
  );
}
