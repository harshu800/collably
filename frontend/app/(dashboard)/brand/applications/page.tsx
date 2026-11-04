"use client";

import Link from "next/link";
import { useCampaigns } from "@/lib/api/queries";
import { LoadingState } from "@/components/states/LoadingState";
import { ErrorState } from "@/components/states/ErrorState";
import { EmptyState } from "@/components/states/EmptyState";

export default function BrandApplicationsPage() {
  const q = useCampaigns({ page: 1, page_size: 50 });
  if (q.isLoading) return <LoadingState />;
  if (q.isError) return <ErrorState onRetry={() => q.refetch()} />;
  if (!q.data || q.data.items.length === 0) {
    return (
      <EmptyState
        title="No campaigns yet"
        description="Applications live under each campaign. Create a campaign first."
      />
    );
  }
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold">Applications</h1>
      <p className="text-sm text-slate-600">
        Pick a campaign to review its applications.
      </p>
      <ul className="flex flex-col gap-2">
        {q.data.items.map((c) => (
          <li key={c.id}>
            <Link
              href={`/brand/campaigns/${c.id}`}
              className="block rounded border border-slate-200 bg-white p-3 text-sm hover:border-brand-500"
            >
              {c.title}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
