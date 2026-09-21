import { useEffect, useState } from "react";
import { fetchIncidents } from "../lib/api";
import type { Incident } from "../types";

const POLL_MS = 5000;

export function useIncidents(limit = 20): Incident[] {
  const [incidents, setIncidents] = useState<Incident[]>([]);

  useEffect(() => {
    let cancelled = false;

    function load() {
      fetchIncidents(limit)
        .then((data) => {
          if (!cancelled) setIncidents(data);
        })
        .catch(() => undefined);
    }

    load();
    const timer = setInterval(load, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [limit]);

  return incidents;
}
