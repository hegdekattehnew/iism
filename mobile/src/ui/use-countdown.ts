import { useEffect, useState } from "react";

/**
 * Seconds left until a moment, counted from a **deadline**, not by ticks. A tick counter drifts
 * and stops when the app is in the background; a deadline is right however the app was suspended
 * (the web's `useCountdown`, ADR-066, for the same reason).
 */
export function useCountdown() {
  const [deadline, setDeadline] = useState(0);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (deadline <= Date.now()) return;
    const timer = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(timer);
  }, [deadline]);

  return {
    seconds: Math.max(0, Math.ceil((deadline - now) / 1000)),
    start: (seconds: number) => {
      const at = Date.now();
      setNow(at);
      setDeadline(at + Math.max(0, seconds) * 1000);
    },
  };
}
