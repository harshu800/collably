"use client";

import Link from "next/link";
import { useCampaigns } from "@/lib/api/queries";
import { LoadingState } from "@/components/states/LoadingState";
import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { formatINR } from "@/lib/money";

export default function PublicCampaignsPage() {
  const q = useCampaigns({ page: 1, page_size: 20 });
  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-6 px-6 py-10">
      <header>
        <h1 className="text-3xl font-bold">Open campaigns</h1>
        <p className="mt-2 text-sm text-slate-600">
          Only brands with onboarded profiles can post campaigns.
        </p>
      </header>
      {q.isLoading ? (
        <LoadingState label="Loading campaigns" />
      ) : q.isError ? (
        <ErrorState
          description="Could not reach the server."
          onRetry={() => q.refetch()}
        />
      ) : !q.data || q.data.items.length === 0 ? (
        <EmptyState
          title="No open campaigns"
          description="Nothing to apply to right now. Check back soon."
        />
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2">
          {q.data.items.map((c) => (
            <li key={c.id}>
              <Link
                href={`/campaigns/${c.id}`}
                className="block focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-600 focus-visible:ring-offset-2"
              >
                <Card className="hover:border-brand-500">
                  <CardContent className="flex flex-col gap-1.5">
                    <p className="text-base font-semibold text-slate-900">
                      {c.title}
                    </p>
                    <p className="text-sm text-slate-600">
                      {formatINR(c.budget_paise)} • {c.type} •{" "}
                      {c.number_of_creators} creator
                      {c.number_of_creators > 1 ? "s" : ""}
                    </p>
                    <div className="flex flex-wrap gap-1">
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
    </main>
  );
}
