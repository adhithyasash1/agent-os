import * as React from "react";

import { cn } from "@/lib/utils";

export type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost";
};

const styles: Record<NonNullable<ButtonProps["variant"]>, string> = {
  primary:
    "bg-gradient-to-r from-accent to-gold text-slate-950 shadow-panel hover:opacity-95",
  secondary:
    "bg-white/10 text-white ring-1 ring-white/10 hover:bg-white/15",
  ghost:
    "bg-transparent text-white ring-1 ring-line hover:bg-white/5"
};

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", ...props }, ref) => (
    <button
      ref={ref}
      className={cn(
        "inline-flex items-center justify-center rounded-full px-4 py-2 text-sm font-semibold transition",
        styles[variant],
        className
      )}
      {...props}
    />
  )
);

Button.displayName = "Button";
