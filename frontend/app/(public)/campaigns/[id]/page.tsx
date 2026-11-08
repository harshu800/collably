"use client";

import * as React from "react";
import Link from "next/link";
import { useAuth } from "@clerk/nextjs";
import { useCampaign, useMyProfile, useSubmitApplication } from "@/lib/api/queries";
import { LoadingState } from "@/components/states/LoadingState";
import { ErrorState } from "@/components/states/ErrorState";
import { EmptyState } from "@/components/states/EmptyState";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
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
      <CampaignApplyAction campaignId={c.id} status={c.status} />
    </main>
  );
}

function CampaignApplyAction({
  campaignId,
  status,
}: {
  campaignId: string;
  status: string;
}) {
  const { isLoaded, isSignedIn } = useAuth();
  const profile = useMyProfile({ enabled: isLoaded && isSignedIn === true });
  const apply = useSubmitApplication(campaignId);
  const [submitted, setSubmitted] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  if (status !== "open") {
    return (
      <p className="text-sm text-slate-600">
        This campaign is no longer accepting applications.
      </p>
    );
  }

  if (!isLoaded) return <LoadingState label="Checking your account" />;

  if (!isSignedIn) {
    return (
      <Link
        href={`/sign-in?next=${encodeURIComponent(`/campaigns/${campaignId}`)}`}
        className="inline-flex h-11 items-center justify-center rounded-md bg-brand-600 px-5 text-base font-medium text-white hover:bg-brand-500"
      >
        Sign in to apply for collaboration
      </Link>
    );
  }

  if (profile.isLoading) return <LoadingState label="Checking your account" />;
  if (profile.isError) {
    return (
      <ErrorState
        description="Could not check your account before applying."
        onRetry={() => profile.refetch()}
      />
    );
  }
  if (profile.data?.role === null) {
    return (
      <Link
        href="/onboarding"
        className="inline-flex h-11 items-center justify-center rounded-md bg-brand-600 px-5 text-base font-medium text-white hover:bg-brand-500"
      >
        Finish setup to apply
      </Link>
    );
  }
  if (profile.data?.role !== "creator") {
    return (
      <p className="text-sm text-slate-600">
        Only creator accounts can apply to campaigns.
      </p>
    );
  }

  if (submitted) {
    return (
      <div className="flex flex-col items-start gap-2">
        <p className="text-sm font-medium text-green-700">
          Your application has been sent.
        </p>
        <Link
          href="/creator/applications"
          className="text-sm font-medium text-brand-600 underline"
        >
          View your applications
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-start gap-2">
      {error ? (
        <p role="alert" className="text-sm text-red-700">
          {error}
        </p>
      ) : null}
      <Button
        disabled={apply.isPending}
        onClick={async () => {
          setError(null);
          try {
            await apply.mutateAsync({ pitch: "I would like to apply." });
            setSubmitted(true);
          } catch (submissionError) {
            setError(
              submissionError instanceof Error
                ? submissionError.message
                : "Your application could not be sent.",
            );
          }
        }}
      >
        {apply.isPending ? "Applying…" : "Apply for collaboration"}
      </Button>
    </div>
  );
}
