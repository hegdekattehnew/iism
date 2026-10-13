import { useCallback, useEffect, useState } from "react";

/**
 * Seconds left until something may be tried again, counting down by itself.
 *
 * Built on a deadline rather than a decrementing counter: a tab in the background throttles its
 * timers, so a counter would run slow and a person returning to it would be told to wait for time
 * that has already passed. The server is the authority (a 429 with `Retry-After`); this only keeps
 * the button honest so nobody has to press it to find out.
 */
export function useCountdown(): { remaining: number; start: (seconds: number) => void } {
  const [until, setUntil] = useState(0);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (until <= Date.now()) return;
    const id = setInterval(() => {
      const t = Date.now();
      setNow(t);
      if (t >= until) clearInterval(id);
    }, 500);
    return () => clearInterval(id);
  }, [until]);

  const start = useCallback((seconds: number) => {
    const t = Date.now();
    setNow(t);
    setUntil(seconds > 0 ? t + seconds * 1000 : 0);
  }, []);

  return { remaining: Math.max(0, Math.ceil((until - now) / 1000)), start };
}
