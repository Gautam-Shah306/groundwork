import type { ReactNode } from "react";

export interface EyebrowProps {
  children: ReactNode;
  className?: string;
}

export function Eyebrow({ children, className = "" }: EyebrowProps) {
  return (
    <span
      className={`inline-block font-sans text-[9px] font-bold uppercase tracking-[0.12em] text-muted ${className}`.trim()}
    >
      {children}
    </span>
  );
}
