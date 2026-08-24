import type { HTMLAttributes, ReactNode } from "react";

export type BadgeTone = "a" | "b" | "neutral";

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  children: ReactNode;
  tone?: BadgeTone;
  who?: Exclude<BadgeTone, "neutral">;
}

const toneClasses: Record<BadgeTone, string> = {
  a: "bg-rose-100 text-rose-700",
  b: "bg-sky-100 text-sky-700",
  neutral: "bg-gray-100 text-gray-700",
};

export default function Badge({
  children,
  className,
  tone = "neutral",
  who,
  ...props
}: BadgeProps) {
  const resolvedTone = who ?? tone;

  return (
    <span
      className={[
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
        toneClasses[resolvedTone],
        className,
      ]
        .filter(Boolean)
        .join(" ")}
      {...props}
    >
      {children}
    </span>
  );
}
