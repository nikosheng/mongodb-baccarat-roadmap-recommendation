import { useAppStore } from "../../stores/useAppStore";

const STATUS_CONFIG = {
  connected: { color: "bg-green-500", label: "Connected" },
  connecting: { color: "bg-yellow-500 animate-pulse", label: "Connecting..." },
  disconnected: { color: "bg-red-500", label: "Reconnecting..." },
};

export function ConnectionStatus() {
  const wsStatus = useAppStore((s) => s.wsStatus);
  const latency = useAppStore((s) => s.wsLatencyMs);
  const cfg = STATUS_CONFIG[wsStatus];

  return (
    <div className="flex items-center gap-2 text-sm text-text-muted">
      <span className={`w-2.5 h-2.5 rounded-full ${cfg.color}`} />
      <span>🔌 WebSocket: {cfg.label}</span>
      {latency !== null && wsStatus === "connected" && <span>延遲: {latency}ms</span>}
    </div>
  );
}
