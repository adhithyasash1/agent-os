import * as React from "react";

import { cn } from "@/lib/utils";

export const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => (
  <textarea
    ref={ref}
    className={cn(
      "min-h-36 w-full rounded-3xl border border-line bg-white/5 px-4 py-4 text-sm text-white outline-none transition placeholder:text-muted focus:border-accent",
      className
    )}
    {...props}
  />
));

Textarea.displayName = "Textarea";
