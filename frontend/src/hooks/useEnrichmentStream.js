import { useState, useRef, useCallback } from "react";

export function useEnrichmentStream() {
  const [progress, setProgress] = useState(0);
  const [steps, setSteps] = useState([]);
  const [log, setLog] = useState([]);
  const [sectionsReady, setSectionsReady] = useState({});
  const [streaming, setStreaming] = useState(false);
  const [complete, setComplete] = useState(false);
  const wsRef = useRef(null);

  const startStream = useCallback((companyId) => {
    if (wsRef.current) {
      wsRef.current.close();
    }

    setStreaming(true);
    setComplete(false);
    setProgress(0);
    setSteps([]);
    setLog([]);
    setSectionsReady({});

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${protocol}//${window.location.host}/v1/ws/enrichment/${companyId}`);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        switch (msg.type) {
          case "step_complete":
            setProgress(msg.overall_progress_pct || 0);
            setSteps((prev) => [...prev, { step: msg.step, status: "complete", duration_ms: msg.duration_ms }]);
            if (msg.log_message) setLog((prev) => [...prev, msg.log_message]);
            break;
          case "section_ready":
            setSectionsReady((prev) => ({ ...prev, [msg.section]: true }));
            break;
          case "enrichment_complete":
            setProgress(100);
            setComplete(true);
            setStreaming(false);
            break;
          case "enrichment_error":
            if (msg.fallback) setLog((prev) => [...prev, `⚠ ${msg.error} — ${msg.fallback}`]);
            break;
          default:
            break;
        }
      } catch {
        // ignore parse errors
      }
    };

    ws.onclose = () => {
      setStreaming(false);
    };

    ws.onerror = () => {
      setStreaming(false);
    };
  }, []);

  const stop = useCallback(() => {
    wsRef.current?.close();
    setStreaming(false);
  }, []);

  return { progress, steps, log, sectionsReady, streaming, complete, startStream, stop };
}
