import * as React from "react";
import { cn } from "@/lib/utils";

export function Avatar({
  className,
  initials,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { initials?: string }) {
  return (
    <div
      className={cn(
        "flex h-9 w-9 items-center justify-center rounded-full bg-brand-100 text-sm font-medium uppercase text-brand-700",
        className,
      )}
      aria-hidden="true"
      {...props}
    >
      {initials ?? "?"}
    </div>
  );
}
