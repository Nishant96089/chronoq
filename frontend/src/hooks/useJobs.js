import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listJobs,
  getJob,
  createJob,
  updateJob,
  deleteJob,
  triggerJob,
  listJobExecutions,
} from "../api/jobs";

// Query keys — React Query uses these to cache and invalidate.
// Centralizing them avoids typos and makes invalidation predictable.
export const jobKeys = {
  all: ["jobs"],
  detail: (id) => ["jobs", id],
  executions: (id) => ["jobs", id, "executions"],
};

export function useJobs() {
  return useQuery({
    queryKey: jobKeys.all,
    queryFn: listJobs,
  });
}

export function useJob(publicId) {
  return useQuery({
    queryKey: jobKeys.detail(publicId),
    queryFn: () => getJob(publicId),
    enabled: Boolean(publicId), // don't run until we have an id
  });
}

export function useJobExecutions(publicId, options = {}) {
  return useQuery({
    queryKey: jobKeys.executions(publicId),
    queryFn: () => listJobExecutions(publicId),
    enabled: Boolean(publicId),
    ...options, // lets callers pass refetchInterval for polling
  });
}

export function useCreateJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createJob,
    onSuccess: () => {
      // After creating, refresh the jobs list.
      qc.invalidateQueries({ queryKey: jobKeys.all });
    },
  });
}

export function useUpdateJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ publicId, payload }) => updateJob(publicId, payload),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: jobKeys.all });
      qc.invalidateQueries({ queryKey: jobKeys.detail(variables.publicId) });
    },
  });
}

export function useDeleteJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteJob,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: jobKeys.all });
    },
  });
}

export function useTriggerJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: triggerJob,
    onSuccess: (_data, publicId) => {
      // Refresh executions so the new run shows up.
      qc.invalidateQueries({ queryKey: jobKeys.executions(publicId) });
    },
  });
}
