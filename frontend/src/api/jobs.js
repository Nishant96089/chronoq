import client from "./client";

export async function listJobs() {
  const { data } = await client.get("/jobs/");
  return data; // { count, next, previous, results: [...] }
}

export async function getJob(publicId) {
  const { data } = await client.get(`/jobs/${publicId}/`);
  return data;
}

export async function createJob(payload) {
  const { data } = await client.post("/jobs/", payload);
  return data;
}

export async function updateJob(publicId, payload) {
  const { data } = await client.patch(`/jobs/${publicId}/`, payload);
  return data;
}

export async function deleteJob(publicId) {
  await client.delete(`/jobs/${publicId}/`);
}

export async function triggerJob(publicId) {
  const { data } = await client.post(`/jobs/${publicId}/trigger/`);
  return data; // the created execution
}

export async function listJobExecutions(publicId) {
  const { data } = await client.get(`/jobs/${publicId}/executions/`);
  return data; // { count, next, previous, results: [...] }
}
