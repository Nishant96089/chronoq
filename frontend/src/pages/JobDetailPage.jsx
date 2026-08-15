import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  useJob,
  useJobExecutions,
  useTriggerJob,
  useUpdateJob,
  useDeleteJob,
} from "../hooks/useJobs";
import Layout from "../components/Layout";
import ExecutionTable from "../components/ExecutionTable";
import ConfirmDialog from "../components/ConfirmDialog";
import { formatDateTime } from "../utils/time";

function DetailRow({ label, children }) {
  return (
    <div className="flex justify-between py-2 border-b border-gray-100 last:border-0">
      <span className="text-sm text-gray-500">{label}</span>
      <span className="text-sm text-gray-900 text-right">{children}</span>
    </div>
  );
}

export default function JobDetailPage() {
  const { publicId } = useParams();
  const navigate = useNavigate();

  const { data: job, isLoading, isError } = useJob(publicId);
  const { data: execData, isRefetching } = useJobExecutions(publicId, {
    refetchInterval: 5000,
  });

  const triggerJob = useTriggerJob();
  const updateJob = useUpdateJob();
  const deleteJob = useDeleteJob();

  const [confirmDelete, setConfirmDelete] = useState(false);

  async function handleTrigger() {
    await triggerJob.mutateAsync(publicId);
  }

  async function handleToggleActive() {
    await updateJob.mutateAsync({
      publicId,
      payload: { is_active: !job.is_active },
    });
  }

  async function handleDeleteConfirmed() {
    await deleteJob.mutateAsync(publicId);
    navigate("/jobs");
  }

  if (isLoading) {
    return (
      <Layout>
        <p className="text-gray-500 text-sm py-12 text-center">Loading job…</p>
      </Layout>
    );
  }

  if (isError || !job) {
    return (
      <Layout>
        <div className="text-red-600 bg-red-50 border border-red-200 rounded-lg
                        px-4 py-3 text-sm">
          Job not found.
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <button
        onClick={() => navigate("/jobs")}
        className="text-sm text-gray-500 hover:text-gray-700 mb-2"
      >
        ← Back to jobs
      </button>

      <div className="flex items-start justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">{job.name}</h2>
          <p className="text-sm text-gray-500 mt-1 font-mono break-all">
            {job.target_url}
          </p>
        </div>
        <div className="flex gap-2 flex-shrink-0">
          <button
            onClick={handleTrigger}
            disabled={triggerJob.isPending}
            className="bg-indigo-600 text-white text-sm font-medium px-4 py-2
                       rounded-lg hover:bg-indigo-700 disabled:opacity-50
                       transition"
          >
            {triggerJob.isPending ? "Running…" : "Run now"}
          </button>
          <button
            onClick={handleToggleActive}
            disabled={updateJob.isPending}
            className="text-sm font-medium px-4 py-2 rounded-lg border
                       border-gray-300 hover:bg-gray-50 transition"
          >
            {job.is_active ? "Deactivate" : "Activate"}
          </button>
          <button
            onClick={() => setConfirmDelete(true)}
            disabled={deleteJob.isPending}
            className="text-sm font-medium px-4 py-2 rounded-lg border
                       border-red-200 text-red-600 hover:bg-red-50 transition"
          >
            Delete
          </button>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-6 mb-8">
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-3">
            Configuration
          </h3>
          <DetailRow label="Method">{job.http_method}</DetailRow>
          <DetailRow label="Schedule">
            <code className="font-mono text-xs">{job.schedule_cron}</code>
          </DetailRow>
          <DetailRow label="Next run">
            {formatDateTime(job.next_fire_at)}
          </DetailRow>
          <DetailRow label="Timeout">{job.timeout_seconds}s</DetailRow>
          <DetailRow label="Active">
            {job.is_active ? (
              <span className="text-green-600 font-medium">Yes</span>
            ) : (
              <span className="text-gray-400">No</span>
            )}
          </DetailRow>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-3">
            Retry policy
          </h3>
          <DetailRow label="Max retries">{job.max_retries}</DetailRow>
          <DetailRow label="Backoff">{job.retry_backoff_seconds}s</DetailRow>
          <DetailRow label="Created">
            {formatDateTime(job.created_at)}
          </DetailRow>
        </div>
      </div>

      <h3 className="text-lg font-semibold text-gray-900 mb-3">
        Execution history
      </h3>
      <ExecutionTable
        executions={execData?.results}
        isRefetching={isRefetching}
      />

      <ConfirmDialog
        open={confirmDelete}
        title="Delete job"
        message={`Delete "${job.name}"? This permanently removes the job and its execution history.`}
        confirmLabel="Delete"
        destructive
        busy={deleteJob.isPending}
        onConfirm={handleDeleteConfirmed}
        onCancel={() => setConfirmDelete(false)}
      />
    </Layout>
  );
}
