"use client";

import * as React from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import { useQuery } from "@tanstack/react-query";
import { useApi } from "@/lib/api/useApi";
import { DashboardNav } from "@/components/layout/DashboardNav";
import { LoadingState } from "@/components/states/LoadingState";
import { ErrorState } from "@/components/states/ErrorState";
import { Button } from "@/components/ui/button";

type Role = "creator" | "brand" | "admin";

interface MeOut {
  id: string;
  email: string;
  role: Role | null;
  clerk_user_id?: string;
  is_active?: boolean;
}

function roleForPath(pathname: string): Role | null {
  if (pathname.startsWith("/creator")) return "creator";
  if (pathname.startsWith("/brand")) return "brand";
  if (pathname.startsWith("/admin")) return "admin";
  return null;
}

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const { isLoaded, isSignedIn } = useAuth();
  const api = useApi();
  const requiredRole = roleForPath(pathname);

  React.useEffect(() => {
    if (isLoaded && !isSignedIn) {
      router.replace(`/sign-in?next=${encodeURIComponent(pathname)}`);
    }
  }, [isLoaded, isSignedIn, pathname, router]);

  const meQuery = useQuery<MeOut>({
    queryKey: ["me"],
    queryFn: () => api.get<MeOut>("/users/me"),
    enabled: Boolean(isLoaded && isSignedIn),
  });

  React.useEffect(() => {
    if (meQuery.data && meQuery.data.role === null) {
      router.replace("/onboarding");
    }
  }, [meQuery.data, router]);

  if (!isLoaded || meQuery.isLoading || !isSignedIn) {
    return (
      <main className="mx-auto max-w-3xl p-10">
        <LoadingState
          label={isLoaded && !isSignedIn ? "Redirecting to sign-in" : undefined}
        />
      </main>
    );
  }

  if (meQuery.isError || !meQuery.data) {
    return (
      <main className="mx-auto max-w-3xl p-10">
        <ErrorState
          description="Could not load your account."
          onRetry={() => meQuery.refetch()}
        />
      </main>
    );
  }

  const me = meQuery.data;

  if (me.role === null) {
    return (
      <main className="mx-auto max-w-3xl p-10">
        <LoadingState label="Redirecting to onboarding" />
      </main>
    );
  }

  if (requiredRole && me.role !== requiredRole) {
    const roleHome =
      me.role === "creator"
        ? "/creator/overview"
        : me.role === "brand"
        ? "/brand/overview"
        : "/admin/overview";
    return (
      <main className="mx-auto flex min-h-screen max-w-xl flex-col items-center justify-center gap-4 p-10 text-center">
        <ErrorState
          title="403 — You cannot view this section"
          description={`This area is for ${requiredRole} accounts. Your account is a ${me.role}.`}
        />
        <Button onClick={() => router.push(roleHome)}>
          Go to your {me.role} dashboard
        </Button>
      </main>
    );
  }

  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      <DashboardNav role={me.role} />
      <section className="flex-1 bg-white p-6">{children}</section>
    </div>
  );
}
