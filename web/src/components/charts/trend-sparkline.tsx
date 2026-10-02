"use client";

export interface TrendPoint {
  bucket: string;
  value: number;
}

/**
 * A small multi-point trend line. Built this sprint and left unwired -- no
 * dashboard has a time-bucketed backend query yet (that is a genuinely new
 * aggregation, deferred as a fast-follow), so nothing calls this today.
 *
 * The min/max scaling below picks a *screen position* for each point; it
 * never invents a data value, the same distinction `Progress`'s
 * width-from-percent already draws.
 */
export function TrendSparkline({ points, label }: { points: TrendPoint[]; label: string }) {
  if (points.length === 0) {
    return null;
  }
  const width = 240;
  const height = 48;
  const values = points.map((p) => p.value);
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const range = max - min || 1;
  const step = points.length > 1 ? width / (points.length - 1) : 0;
  const coords = points
    .map((p, i) => {
      const x = points.length > 1 ? i * step : width / 2;
      const y = height - ((p.value - min) / range) * height;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-muted">{label}</p>
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={label}
        className="mt-1"
      >
        <polyline points={coords} fill="none" strokeWidth={2} style={{ stroke: "var(--brand)" }} />
      </svg>
    </div>
  );
}
