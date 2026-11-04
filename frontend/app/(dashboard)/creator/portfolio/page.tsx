"use client";

import { useMyProfile } from "@/lib/api/queries";
import { LoadingState } from "@/components/states/LoadingState";
import { ErrorState } from "@/components/states/ErrorState";
import { EmptyState } from "@/components/states/EmptyState";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface Link {
  label: string;
  url: string;
}

export default function CreatorPortfolioPage() {
  const q = useMyProfile();
  if (q.isLoading) return <LoadingState />;
  if (q.isError)
    return (
      <ErrorState
        description="Could not load your portfolio."
        onRetry={() => q.refetch()}
      />
    );
  const creator = q.data?.creator as
    | { portfolio_links?: Link[]; social_handles?: unknown[] }
    | undefined;
  const links = creator?.portfolio_links ?? [];
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold">Portfolio</h1>
      <Card>
        <CardHeader>
          <CardTitle>Links</CardTitle>
        </CardHeader>
        <CardContent>
          {links.length === 0 ? (
            <EmptyState
              title="No portfolio links yet"
              description="Add portfolio links through onboarding to show brands your work."
            />
          ) : (
            <ul className="flex flex-col gap-2 text-sm">
              {links.map((l) => (
                <li key={l.url}>
                  <a
                    className="text-brand-600 underline"
                    href={l.url}
                    target="_blank"
                    rel="noreferrer noopener"
                  >
                    {l.label}
                  </a>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
