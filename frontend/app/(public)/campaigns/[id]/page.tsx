"use client";

import { useCampaign } from "@/lib/api/queries";
import { LoadingState } from "@/components/states/LoadingState";
import { ErrorState } from "@/components/states/ErrorState";
import { EmptyState } from "@/components/states/EmptyState";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatINR } from "@/lib/money";

export default function CampaignDetailPage({
  params,
}: {
  params: { id: string };
}) {
  const q = useCampaign(params.id);
  if (q.isLoading) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-10">
        <LoadingState label="Loading campaign" />
      </main>
    );
  }
  if (q.isError) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-10">
        <ErrorState
          description="This campaign could not be loaded."
          onRetry={() => q.refetch()}
        />
      </main>
    );
  }
  const c = q.data;
  if (!c) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-10">
        <EmptyState title="Not found" />
      </main>
    );
  }
  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 px-6 py-10">
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-bold">{c.title}</h1>
        <div className="flex flex-wrap gap-1">
          <Badge tone="info">{c.type}</Badge>
          <Badge>{c.status}</Badge>
          {c.niches.map((n) => (
            <Badge key={n}>{n}</Badge>
          ))}
        </div>
      </header>
      {c.description ? (
        <Card>
          <CardContent className="whitespace-pre-wrap text-sm text-slate-700">
            {c.description}
          </CardContent>
        </Card>
      ) : null}
      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Budget</CardTitle>
          </CardHeader>
          <CardContent>{formatINR(c.budget_paise)}</CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Revision limit</CardTitle>
          </CardHeader>
          <CardContent>{c.revision_limit}</CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Creators needed</CardTitle>
          </CardHeader>
          <CardContent>{c.number_of_creators}</CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Deadline</CardTitle>
          </CardHeader>
          <CardContent>
            {c.submission_deadline
              ? new Date(c.submission_deadline).toLocaleString()
              : "Not set"}
          </CardContent>
        </Card>
      </div>
      {c.usage_rights ? (
        <Card>
          <CardHeader>
            <CardTitle>Usage rights</CardTitle>
          </CardHeader>
          <CardContent className="whitespace-pre-wrap text-sm text-slate-700">
            {c.usage_rights}
          </CardContent>
        </Card>
      ) : null}
    </main>
  );
}
