"use client";

import { useCreator } from "@/lib/api/queries";
import { LoadingState } from "@/components/states/LoadingState";
import { ErrorState } from "@/components/states/ErrorState";
import { EmptyState } from "@/components/states/EmptyState";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatINR } from "@/lib/money";

export default function CreatorDetailPage({
  params,
}: {
  params: { id: string };
}) {
  const q = useCreator(params.id);
  if (q.isLoading) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-10">
        <LoadingState label="Loading creator" />
      </main>
    );
  }
  if (q.isError) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-10">
        <ErrorState
          description="This creator could not be loaded."
          onRetry={() => q.refetch()}
        />
      </main>
    );
  }
  const c = q.data;
  if (!c) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-10">
        <EmptyState title="Not found" description="This creator does not exist." />
      </main>
    );
  }
  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 px-6 py-10">
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-bold">
          {c.display_name ?? "Unnamed creator"}
        </h1>
        <p className="text-slate-600">
          {[c.city, c.state].filter(Boolean).join(", ") || "Location unspecified"}
        </p>
        <div className="flex flex-wrap gap-1">
          {c.does_ugc ? <Badge tone="info">UGC</Badge> : null}
          {c.does_influencer ? <Badge tone="info">Influencer</Badge> : null}
          {c.niches.map((n) => (
            <Badge key={n}>{n}</Badge>
          ))}
        </div>
      </header>
      {c.bio ? (
        <Card>
          <CardContent className="whitespace-pre-wrap text-sm text-slate-700">
            {c.bio}
          </CardContent>
        </Card>
      ) : null}
      <div className="grid gap-4 sm:grid-cols-2">
        {c.starting_rate_paise != null ? (
          <Card>
            <CardHeader>
              <CardTitle>Starting rate</CardTitle>
            </CardHeader>
            <CardContent>{formatINR(c.starting_rate_paise)}</CardContent>
          </Card>
        ) : null}
        {c.content_types.length ? (
          <Card>
            <CardHeader>
              <CardTitle>Content types</CardTitle>
            </CardHeader>
            <CardContent>{c.content_types.join(", ")}</CardContent>
          </Card>
        ) : null}
      </div>
      {c.portfolio_links.length ? (
        <section>
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
            Portfolio
          </h2>
          <ul className="flex flex-col gap-1 text-sm">
            {c.portfolio_links.map((p) => (
              <li key={p.url}>
                <a
                  href={p.url}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="text-brand-600 underline"
                >
                  {p.label}
                </a>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {c.social_handles.length ? (
        <section>
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
            Social handles
          </h2>
          <ul className="flex flex-col gap-1 text-sm">
            {c.social_handles.map((s) => (
              <li key={`${s.platform}-${s.handle}`}>
                <span className="font-medium">{s.platform}:</span> {s.handle}{" "}
                <Badge tone="warning">unverified</Badge>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </main>
  );
}
