"use client";

import * as React from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useAuth, useUser } from "@clerk/nextjs";
import { useApi } from "@/lib/api/useApi";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { LoadingState } from "@/components/states/LoadingState";
import { Alert } from "@/components/ui/alert";

type Role = "creator" | "brand" | "admin";

interface MeOut {
  id: string;
  email: string;
  role: Role | null;
  clerk_user_id?: string;
  is_active?: boolean;
}

const ROLE_HOME: Record<Role, string> = {
  creator: "/creator/overview",
  brand: "/brand/overview",
  admin: "/admin/overview",
};

export default function OnboardingPage() {
  const router = useRouter();
  const { isLoaded, isSignedIn } = useAuth();
  const { user } = useUser();
  const api = useApi();
  const [me, setMe] = React.useState<MeOut | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [submitting, setSubmitting] = React.useState<Role | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!isLoaded) return;
    if (!isSignedIn) {
      router.replace("/sign-in");
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const data = await api.get<MeOut>("/users/me");
        if (cancelled) return;
        if (data.role) {
          router.replace(ROLE_HOME[data.role]);
          return;
        }
        setMe(data);
      } catch (e) {
        if (cancelled) return;
        setError(
          e instanceof Error ? e.message : "Could not load your account.",
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [isLoaded, isSignedIn, api, router]);

  async function pick(role: "creator" | "brand") {
    setError(null);
    setSubmitting(role);
    try {
      await api.post<MeOut>("/users/me/role", { body: { role } });
      router.replace(ROLE_HOME[role]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save your role.");
      setSubmitting(null);
    }
  }

  if (!isLoaded || loading) {
    return (
      <main className="mx-auto flex max-w-xl flex-col gap-6 px-6 py-10">
        <LoadingState />
      </main>
    );
  }

  return (
    <main className="mx-auto flex max-w-3xl flex-col items-center gap-8 px-6 py-16">
      <Image
        src="/mascot/collably.png"
        alt=""
        width={160}
        height={160}
        onError={(e) => {
          (e.currentTarget as HTMLImageElement).style.display = "none";
        }}
      />
      <header className="flex flex-col items-center gap-2 text-center">
        <h1 className="text-2xl font-bold">Pick what fits you best</h1>
        <p className="text-sm text-slate-600">
          You can only choose once. {user?.primaryEmailAddress?.emailAddress ?? me?.email ?? ""}
        </p>
      </header>
      {error ? <Alert tone="danger">{error}</Alert> : null}
      <div className="grid w-full gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>I create content</CardTitle>
            <CardDescription>
              Build a creator profile and apply to brand campaigns.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button
              onClick={() => pick("creator")}
              disabled={submitting !== null}
              size="lg"
              aria-label="Continue as a creator"
            >
              {submitting === "creator" ? "Saving…" : "Continue as creator"}
            </Button>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>I run a brand</CardTitle>
            <CardDescription>
              Post campaigns and collaborate with vetted creators.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button
              onClick={() => pick("brand")}
              disabled={submitting !== null}
              size="lg"
              aria-label="Continue as a brand"
            >
              {submitting === "brand" ? "Saving…" : "Continue as brand"}
            </Button>
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
