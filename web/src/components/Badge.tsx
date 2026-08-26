import type { HTMLAttributes, ReactNode } from "react";

export type BadgeTone = "a" | "b" | "neutral";

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  children: ReactNode;
  tone?: BadgeTone;
  who?: Exclude<BadgeTone, "neutral">;
}

const toneClasses: Record<BadgeTone, string> = {
  a: "bg-coral-100 text-coral-700",
  b: "bg-lavender-100 text-slate-700",
  neutral: "bg-stone-100 text-stone-700",
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
