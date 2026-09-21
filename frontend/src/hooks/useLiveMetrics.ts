import { useEffect, useRef, useState } from "react";
import { fetchSummary, fetchTimeseries, WS_URL } from "../lib/api";
import type { MetricsSummary, TimeseriesPoint, WebSocketTick } from "../types";

const MAX_POINTS = 60; // ~10 minutes of 10s buckets — enough history without slowing the chart down
const RECONNECT_DELAY_MS = 3000;

interface LiveMetricsState {
  summary: MetricsSummary | null;
  points: TimeseriesPoint[];
  connected: boolean;
}

function appendPoint(points: TimeseriesPoint[], incoming: TimeseriesPoint): TimeseriesPoint[] {
  if (points.length > 0 && points[points.length - 1].timestamp === incoming.timestamp) {
    // Same bucket as last time (it hasn't closed yet) — update it in place.
    return [...points.slice(0, -1), incoming];
  }
  const next = [...points, incoming];
  return next.length > MAX_POINTS ? next.slice(next.length - MAX_POINTS) : next;
}

export function useLiveMetrics(): LiveMetricsState {
  const [summary, setSummary] = useState<MetricsSummary | null>(null);
  const [points, setPoints] = useState<TimeseriesPoint[]>([]);
  const [connected, setConnected] = useState(false);
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mounted = useRef(true);

  // Initial REST fetch, so the dashboard shows real numbers and recent
  // history immediately, before the first WebSocket tick arrives.
  useEffect(() => {
    fetchSummary().then(setSummary).catch(() => undefined);
    fetchTimeseries(10, 10)
      .then((res) => setPoints(res.points.slice(-MAX_POINTS)))
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    mounted.current = true;

    function connect() {
      const socket = new WebSocket(WS_URL);
      socketRef.current = socket;

      socket.onopen = () => {
        if (mounted.current) setConnected(true);
      };

      socket.onmessage = (event) => {
        if (!mounted.current) return;
        const tick = JSON.parse(event.data) as WebSocketTick;
        setSummary(tick.summary);
        setPoints((prev) => appendPoint(prev, tick.point));
      };

      socket.onclose = () => {
        if (!mounted.current) return;
        setConnected(false);
        reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY_MS);
      };

      socket.onerror = () => {
        socket.close();
      };
    }

    connect();

    return () => {
      mounted.current = false;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      socketRef.current?.close();
    };
  }, []);

  return { summary, points, connected };
}
