"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

type Toast = {
  id: number;
  title: string;
  description?: string;
  tone?: "success" | "error" | "info";
};

interface ToastContextShape {
  push: (t: Omit<Toast, "id">) => void;
}
const ToastContext = React.createContext<ToastContextShape | null>(null);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = React.useState<Toast[]>([]);
  const push = React.useCallback((t: Omit<Toast, "id">) => {
    const id = Date.now() + Math.floor(Math.random() * 1000);
    setToasts((xs) => [...xs, { id, ...t }]);
    setTimeout(() => {
      setToasts((xs) => xs.filter((x) => x.id !== id));
    }, 5000);
  }, []);
  return (
    <ToastContext.Provider value={{ push }}>
      {children}
      <div
        aria-live="polite"
        aria-atomic="true"
        className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-full max-w-sm flex-col gap-2"
      >
        {toasts.map((t) => (
          <div
            key={t.id}
            className={cn(
              "pointer-events-auto rounded-md border bg-white p-3 shadow-md",
              t.tone === "error" && "border-red-300",
              t.tone === "success" && "border-emerald-300",
              (!t.tone || t.tone === "info") && "border-slate-200",
            )}
          >
            <p className="text-sm font-semibold text-slate-900">{t.title}</p>
            {t.description ? (
              <p className="mt-0.5 text-sm text-slate-600">{t.description}</p>
            ) : null}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextShape {
  const ctx = React.useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}
