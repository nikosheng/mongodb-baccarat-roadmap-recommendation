import { useEffect, useRef } from "react";
import { useAppStore } from "../stores/useAppStore";
import type { MatchResult } from "../api/types";

export function useTableWebSocket(tableId: string | null) {
  const pushMatch = useAppStore((s) => s.pushMatch);
  const pushDerivedMatch = useAppStore((s) => s.pushDerivedMatch);
  const setWsStatus = useAppStore((s) => s.setWsStatus);
  const setWsLatency = useAppStore((s) => s.setWsLatency);
  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef(1000);
  const pingSentAt = useRef<number>(0);

  useEffect(() => {
    if (!tableId) return;
    let closedByUs = false;
    let pingInterval: ReturnType<typeof setInterval>;

    function connect() {
      setWsStatus("connecting");
      const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
      const url = `${proto}//${window.location.host}/ws/table/${tableId}`;
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setWsStatus("connected");
        retryRef.current = 1000;
        pingInterval = setInterval(() => {
          pingSentAt.current = Date.now();
          ws.send("ping");
        }, 20000);
      };

      ws.onmessage = (event) => {
        if (event.data === '{"type":"pong"}') {
          setWsLatency(Date.now() - pingSentAt.current);
          return;
        }
        try {
          const data = JSON.parse(event.data) as MatchResult;
          if (data.type === "match") {
            if (data.topMatches !== undefined || data.noMatch !== undefined) {
              pushMatch(data);
            }
            if (data.derivedMatch) {
              pushDerivedMatch(data.derivedMatch);
            }
          }
        } catch {
          // ignore malformed messages
        }
      };

      ws.onclose = () => {
        setWsStatus("disconnected");
        clearInterval(pingInterval);
        if (!closedByUs) {
          setTimeout(connect, retryRef.current);
          retryRef.current = Math.min(retryRef.current * 2, 8000);
        }
      };

      ws.onerror = () => {
        ws.close();
      };
    }

    connect();

    return () => {
      closedByUs = true;
      clearInterval(pingInterval);
      wsRef.current?.close();
    };
  }, [tableId, pushMatch, pushDerivedMatch, setWsStatus, setWsLatency]);
}
