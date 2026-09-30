"use client";

/**
 * A percentage, as a ring -- the radial restatement of `Progress`'s exact
 * contract (a clamped value, nothing derived) for a single-tile dashboard
 * card where a linear bar reads as an afterthought.
 *
 * Colour is a raw `var(--brand)` reference rather than a Tailwind palette
 * utility, the same way `LevelScale` already writes `var(--brand-contrast)`
 * -- `tokens.test.ts` flags palette *utility classes*, not a CSS custom
 * property lookup.
 */
export function ProgressRing({
  percent,
  label,
  secondary,
  size = "md",
}: {
  percent: number;
  label: string;
  secondary?: string;
  size?: "sm" | "md";
}) {
  const clamped = Math.max(0, Math.min(100, Math.round(percent)));
  const dimension = size === "sm" ? 64 : 88;
  const stroke = size === "sm" ? 7 : 9;
  const radius = dimension / 2 - stroke;
  const center = dimension / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - clamped / 100);

  return (
    <div className="flex items-center gap-3">
      <svg
        width={dimension}
        height={dimension}
        viewBox={`0 0 ${dimension} ${dimension}`}
        role="img"
        aria-label={`${label}: ${clamped}%`}
      >
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          strokeWidth={stroke}
          style={{ stroke: "var(--surface-muted)" }}
        />
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          strokeWidth={stroke}
          strokeLinecap="round"
          style={{ stroke: "var(--brand)" }}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          transform={`rotate(-90 ${center} ${center})`}
        />
        <text
          x={center}
          y={center}
          textAnchor="middle"
          dominantBaseline="central"
          className="fill-foreground"
          style={{ fontSize: size === "sm" ? 13 : 15, fontWeight: 600 }}
        >
          {clamped}%
        </text>
      </svg>
      <div>
        <div className="text-sm font-medium">{label}</div>
        {secondary && <div className="text-xs text-muted">{secondary}</div>}
      </div>
    </div>
  );
}
