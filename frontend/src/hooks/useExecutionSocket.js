import { useEffect, useRef, useState, useCallback } from "react";

/**
 * Opens a WebSocket to stream live execution updates for a job.
 *
 * Returns { status, lastUpdate } where:
 *  - status: "connecting" | "open" | "closed" | "error"
 *  - lastUpdate: the most recent execution_update payload (or null)
 *
 * Handles reconnection with backoff. Designed to complement (not replace)
 * React Query polling — the caller keeps a slow poll as a fallback and uses
 * lastUpdate to trigger fast refetches when live events arrive.
 */
export function useExecutionSocket(jobPublicId, { onUpdate } = {}) {
  const [status, setStatus] = useState("connecting");
  const [lastUpdate, setLastUpdate] = useState(null);
  const wsRef = useRef(null);
  const reconnectRef = useRef({ attempts: 0, timer: null });
  const connectRef = useRef(null);
  const onUpdateRef = useRef(onUpdate);

  // Keep the latest onUpdate without retriggering the effect.
  useEffect(() => {
    onUpdateRef.current = onUpdate;
  }, [onUpdate]);

  const connect = useCallback(() => {
    if (!jobPublicId) return;

    const token = localStorage.getItem("chronoq_token");
    if (!token) {
      setStatus("error");
      return;
    }

    // ws:// for http, wss:// for https. API host from env or default.
    const apiBase =
      import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";
    // Strip trailing /api and swap protocol.
    const httpOrigin = apiBase.replace(/\/api\/?$/, "");
    const wsOrigin = httpOrigin.replace(/^http/, "ws");
    const url = `${wsOrigin}/ws/jobs/${jobPublicId}/executions/?token=${token}`;

    setStatus("connecting");
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setStatus("open");
      reconnectRef.current.attempts = 0; // reset backoff on success
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "execution_update") {
          setLastUpdate(data.execution);
          if (onUpdateRef.current) onUpdateRef.current(data.execution);
        }
      } catch {
        // ignore malformed frames
      }
    };

    ws.onerror = () => {
      setStatus("error");
    };

    ws.onclose = () => {
      setStatus("closed");
      // Exponential backoff reconnect, capped at 30s.
      const attempts = reconnectRef.current.attempts + 1;
      reconnectRef.current.attempts = attempts;
      const delay = Math.min(30000, 1000 * 2 ** (attempts - 1));
      reconnectRef.current.timer = setTimeout(() => connectRef.current?.(), delay);
    };
  }, [jobPublicId]);

  // Keep connectRef current so the reconnect timer always calls the latest
  // connect (avoids a stale self-reference inside the callback).
  useEffect(() => {
    connectRef.current = connect;
  }, [connect]);

  useEffect(() => {
    // Defer the initial connect so we don't call setState synchronously inside
    // the effect body (avoids cascading-render lint rule + is functionally the
    // same — connection happens a tick later).
    const startTimer = setTimeout(() => connect(), 0);
    const reconnect = reconnectRef.current; // capture for cleanup
    return () => {
      clearTimeout(startTimer);
      if (reconnect.timer) clearTimeout(reconnect.timer);
      const ws = wsRef.current;
      if (ws) {
        ws.onclose = null;
        ws.onerror = null;
        if (ws.readyState === WebSocket.CONNECTING) {
          ws.onopen = () => ws.close();
        } else {
          ws.close();
        }
      }
    };
  }, [connect]);

  return { status, lastUpdate };
}