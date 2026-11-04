import * as React from "react";
import { cn } from "@/lib/utils";

export function ErrorState({
  title = "Something went wrong",
  description,
  onRetry,
  className,
}: {
  title?: string;
  description?: string;
  onRetry?: () => void;
  className?: string;
}) {
  return (
    <div
      role="alert"
      aria-live="assertive"
      className={cn(
        "flex min-h-[8rem] flex-col items-center justify-center rounded-md border border-red-200 bg-red-50 p-6 text-center",
        className,
      )}
    >
      <h3 className="text-sm font-semibold text-red-800">{title}</h3>
      {description ? (
        <p className="mt-1 max-w-md text-sm text-red-700">{description}</p>
      ) : null}
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 rounded-md border border-red-300 bg-white px-3 py-1.5 text-sm font-medium text-red-700 hover:bg-red-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500 focus-visible:ring-offset-1"
        >
          Try again
        </button>
      ) : null}
    </div>
  );
}
