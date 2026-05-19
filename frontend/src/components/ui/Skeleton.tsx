import type { CSSProperties } from "react";

type Variant = "text" | "title" | "card" | "row";

type Props = {
  variant?: Variant;
  width?: string | number;
  height?: string | number;
  ariaLabel?: string;
};

/** Lightweight shimmer placeholder. Honors `prefers-reduced-motion` via CSS. */
export function Skeleton({ variant = "text", width, height, ariaLabel }: Props) {
  const style: CSSProperties = {};
  if (width !== undefined) style.width = typeof width === "number" ? `${width}px` : width;
  if (height !== undefined) style.height = typeof height === "number" ? `${height}px` : height;
  return (
    <span
      className={`skeleton skeleton--${variant}`}
      style={style}
      role="status"
      aria-live="polite"
      aria-label={ariaLabel ?? "Loading"}
    />
  );
}

type StackProps = {
  rows?: number;
  variant?: Variant;
};

export function SkeletonStack({ rows = 3, variant = "row" }: StackProps) {
  return (
    <div className="skeleton-stack" role="status" aria-live="polite" aria-label="Loading">
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} variant={variant} />
      ))}
    </div>
  );
}
