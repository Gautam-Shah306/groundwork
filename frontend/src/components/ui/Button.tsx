import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Loader2 } from "lucide-react";

export type ButtonVariant = "primary" | "secondary" | "tertiary" | "destructive";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  loading?: boolean;
  icon?: ReactNode;
}

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary:
    "bg-ink text-surface border border-ink hover:bg-ink/90 active:bg-ink/80",
  secondary:
    "bg-surface text-ink border border-border hover:bg-surface-subtle active:bg-accent-soft",
  tertiary:
    "bg-transparent text-ink border border-transparent hover:bg-surface-subtle active:bg-accent-soft",
  destructive:
    "bg-danger text-surface border border-danger hover:bg-danger/90 active:bg-danger/80",
};

export function Button({
  variant = "primary",
  loading = false,
  disabled = false,
  icon,
  children,
  className = "",
  type = "button",
  ...rest
}: ButtonProps) {
  const isDisabled = disabled || loading;

  return (
    <button
      type={type}
      disabled={isDisabled}
      aria-busy={loading || undefined}
      className={[
        "inline-flex h-9 items-center justify-center gap-2 rounded-control px-3.5 text-[13px] font-medium leading-none transition-colors",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
        "disabled:cursor-not-allowed disabled:opacity-50",
        VARIANT_CLASSES[variant],
        className,
      ]
        .filter(Boolean)
        .join(" ")}
      {...rest}
    >
      {loading ? (
        <Loader2
          size={16}
          strokeWidth={1.75}
          aria-hidden="true"
          className="animate-spin shrink-0"
        />
      ) : (
        icon && <span className="inline-flex shrink-0" aria-hidden="true">{icon}</span>
      )}
      <span>{children}</span>
    </button>
  );
}
