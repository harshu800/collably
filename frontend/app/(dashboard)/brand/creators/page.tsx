"use client";

import Link from "next/link";
import { useCreators } from "@/lib/api/queries";
import { LoadingState } from "@/components/states/LoadingState";
import { ErrorState } from "@/components/states/ErrorState";
import { EmptyState } from "@/components/states/EmptyState";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function BrandCreatorsPage() {
  const q = useCreators({ page: 1, page_size: 30 });
  if (q.isLoading) return <LoadingState />;
  if (q.isError) return <ErrorState onRetry={() => q.refetch()} />;
  if (!q.data || q.data.items.length === 0) {
    return <EmptyState title="No creators yet" />;
  }
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold">Browse creators</h1>
      <ul className="grid gap-3 md:grid-cols-2">
        {q.data.items.map((c) => (
          <li key={c.id}>
            <Link
              href={`/creators/${c.id}`}
              className="block focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-600 focus-visible:ring-offset-2"
            >
              <Card className="hover:border-brand-500">
                <CardContent className="flex flex-col gap-2">
                  <p className="font-semibold">
                    {c.display_name ?? "Unnamed creator"}
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
    </div>
  );
}
