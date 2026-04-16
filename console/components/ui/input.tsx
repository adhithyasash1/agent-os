import * as React from "react";

import { cn } from "@/lib/utils";

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        "w-full rounded-2xl border border-line bg-white/5 px-4 py-3 text-sm text-white outline-none ring-0 transition placeholder:text-muted focus:border-accent",
        className
      )}
      {...props}
    />
  )
);

Input.displayName = "Input";
