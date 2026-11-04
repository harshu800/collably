import * as React from "react";
import { cn } from "@/lib/utils";

export function LoadingState({
  label = "Loading",
  className,
}: {
  label?: string;
  className?: string;
}) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        "flex min-h-[8rem] items-center justify-center rounded-md border border-slate-200 bg-white p-6 text-sm text-slate-500",
        className,
      )}
    >
      <span>{label}…</span>
    </div>
  );
}
