"use client";

import Link from "next/link";
import {
  useCollaborations,
  useMyApplications,
  useMyPayoutMethod,
} from "@/lib/api/queries";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LoadingState } from "@/components/states/LoadingState";
import { ErrorState } from "@/components/states/ErrorState";
import { Alert } from "@/components/ui/alert";

export default function CreatorOverviewPage() {
  const collabs = useCollaborations();
  const apps = useMyApplications();
  const method = useMyPayoutMethod();

  if (collabs.isLoading || apps.isLoading) {
    return <LoadingState />;
  }
  if (collabs.isError || apps.isError) {
    return (
      <ErrorState
        description="Could not load your dashboard."
        onRetry={() => {
          void collabs.refetch();
          void apps.refetch();
        }}
      />
    );
  }

  const active = (collabs.data ?? []).filter(
    (c) =>
      !["completed", "cancelled"].includes(c.status) && c.funding_status !== "funding_failed",
  );
  const pendingApps = (apps.data ?? []).filter((a) =>
    ["submitted", "shortlisted", "invited"].includes(a.status),
  );
  const outstandingDeliverables = active.filter((c) =>
    ["funded", "in_progress"].includes(c.status),
  );
  const awaitingPayout = (collabs.data ?? []).filter(
    (c) => c.status === "approved" && c.payout_status !== "paid",
  );

  const stats = [
    { label: "Active collaborations", value: active.length },
    { label: "Pending applications", value: pendingApps.length },
    {
      label: "Outstanding deliverables",
      value: outstandingDeliverables.length,
    },
    { label: "Pending payouts", value: awaitingPayout.length },
  ];

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">Overview</h1>
        <Link
          href="/creator/profile"
          className="inline-flex h-10 items-center rounded-md bg-brand-600 px-4 text-sm font-medium text-white hover:bg-brand-500"
        >
          Edit profile
        </Link>
      </header>
      {method.data === null ? (
        <Alert tone="warning">
          You have not set a payout method yet. Add one so payouts can be
          released after work is approved.
        </Alert>
      ) : null}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((s) => (
          <Card key={s.label}>
            <CardHeader>
              <CardTitle>{s.label}</CardTitle>
            </CardHeader>
            <CardContent className="text-3xl font-semibold">
              {s.value}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
