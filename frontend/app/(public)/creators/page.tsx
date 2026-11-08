"use client";

import * as React from "react";
import Link from "next/link";
import { useCreators } from "@/lib/api/queries";
import { LoadingState } from "@/components/states/LoadingState";
import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export default function CreatorsPage() {
  const [page, setPage] = React.useState(1);
  const pageSize = 20;
  const q = useCreators({ page, page_size: pageSize });
  const totalPages = Math.ceil((q.data?.total ?? 0) / pageSize);
  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-6 px-6 py-10">
      <header>
        <h1 className="text-3xl font-bold">Browse creators</h1>
        <p className="mt-2 text-sm text-slate-600">
          Public profiles only. Follower counts shown are self-reported and
          marked unverified.
        </p>
      </header>
      {q.isLoading ? (
        <LoadingState label="Loading creators" />
      ) : q.isError ? (
        <ErrorState
          description="Could not reach the server."
          onRetry={() => q.refetch()}
        />
      ) : !q.data || q.data.items.length === 0 ? (
        <EmptyState
          title="No creators yet"
          description="As creators complete onboarding they will appear here."
        />
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2">
          {q.data.items.map((c) => (
            <li key={c.id}>
              <Link
                href={`/creators/${c.id}`}
                className="block focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-600 focus-visible:ring-offset-2"
              >
                <Card className="hover:border-brand-500">
                  <CardContent className="flex flex-col gap-2">
                    <p className="text-base font-semibold text-slate-900">
                      {c.display_name ?? "Unnamed creator"}
                    </p>
                    <p className="text-sm text-slate-500">
                      {[c.city, c.state].filter(Boolean).join(", ") ||
                        "Location unspecified"}
                    </p>
                    <div className="flex flex-wrap gap-1">
                      {c.does_ugc ? <Badge tone="info">UGC</Badge> : null}
                      {c.does_influencer ? (
                        <Badge tone="info">Influencer</Badge>
                      ) : null}
                      {c.niches.slice(0, 3).map((n) => (
                        <Badge key={n}>{n}</Badge>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </Link>
            </li>
          ))}
        </ul>
      )}
      {totalPages > 1 ? (
        <nav
          aria-label="Creator pages"
          className="flex items-center justify-center gap-4"
        >
          <Button
            variant="outline"
            disabled={page === 1}
            onClick={() => setPage((current) => current - 1)}
          >
            Previous
          </Button>
          <span className="text-sm text-slate-600">
            Page {page} of {totalPages}
          </span>
          <Button
            variant="outline"
            disabled={page >= totalPages}
            onClick={() => setPage((current) => current + 1)}
          >
            Next
          </Button>
        </nav>
      ) : null}
    </main>
  );
}
