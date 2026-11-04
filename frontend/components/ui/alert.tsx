import * as React from "react";
import { cn } from "@/lib/utils";

type Tone = "info" | "warning" | "danger" | "success";

const toneClasses: Record<Tone, string> = {
  info: "border-brand-100 bg-brand-50 text-brand-700",
  warning: "border-amber-200 bg-amber-50 text-amber-800",
  danger: "border-red-200 bg-red-50 text-red-800",
  success: "border-emerald-200 bg-emerald-50 text-emerald-800",
};

export function Alert({
  className,
  tone = "info",
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { tone?: Tone }) {
  return (
    <div
      role="status"
      className={cn(
        "rounded-md border p-3 text-sm",
        toneClasses[tone],
        className,
      )}
      {...props}
    />
  );
}

export function AlertTitle({
  className,
  ...props
}: React.HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn("font-semibold", className)} {...props} />;
}

export function AlertDescription({
  className,
  ...props
}: React.HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn("mt-1", className)} {...props} />;
}
