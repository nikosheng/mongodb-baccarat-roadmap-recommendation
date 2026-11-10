import { useEffect, useRef, useState } from "react";
import { useAppStore } from "../stores/useAppStore";

const TARGET_PATTERN_NAME = "長莊連龍";
const ANIMATION_DURATION_MS = 5000;

/**
 * Watches `latestMatch` and returns a non-null key whenever a brand-new
 * "長莊連龍" (long Banker dragon) top match arrives with high confidence.
 *
 * `latestMatch` can be pushed twice for the same round (once from the REST
 * response, once from the WebSocket broadcast - see useAppStore.pushMatch),
 * so we de-dupe on `${shoeId}:${roundNo}` via a ref to guarantee the
 * animation fires exactly once per round, not twice.
 *
 * The returned key is intended to be used as a React `key` prop on the
 * animation component, so each new trigger forces a clean remount/restart
 * of the CSS animation.
 */
export function useLongDragonTrigger(): string | null {
  const latestMatch = useAppStore((s) => s.latestMatch);
  const lastTriggeredRef = useRef<string | null>(null);
  const [activeKey, setActiveKey] = useState<string | null>(null);

  useEffect(() => {
    const top = latestMatch?.topMatches?.[0];
    if (!top || top.name !== TARGET_PATTERN_NAME || top.lowConfidence) return;

    const key = `${latestMatch.shoeId}:${latestMatch.roundNo}`;
    if (lastTriggeredRef.current === key) return;
    lastTriggeredRef.current = key;
    setActiveKey(key);

    const timer = setTimeout(() => setActiveKey(null), ANIMATION_DURATION_MS);
    return () => clearTimeout(timer);
  }, [latestMatch]);

  return activeKey;
}
