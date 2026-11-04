"use client";

import { useCollaborations } from "@/lib/api/queries";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LoadingState } from "@/components/states/LoadingState";
import { ErrorState } from "@/components/states/ErrorState";

export default function BrandOverviewPage() {
  const q = useCollaborations();
  if (q.isLoading) return <LoadingState />;
  if (q.isError) return <ErrorState onRetry={() => q.refetch()} />;
  const rows = q.data ?? [];
  const active = rows.filter(
    (c) => !["completed", "cancelled"].includes(c.status),
  );
  const funded = rows.filter((c) => c.funding_status === "funding_confirmed");
  const awaitingReview = rows.filter((c) => c.status === "in_review");
  const stats = [
    { label: "Active collaborations", value: active.length },
    { label: "Funded collaborations", value: funded.length },
    { label: "Awaiting review", value: awaitingReview.length },
    { label: "Total", value: rows.length },
  ];
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold">Overview</h1>
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
