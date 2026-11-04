"use client";

import Link from "next/link";
import { useCampaigns } from "@/lib/api/queries";
import { LoadingState } from "@/components/states/LoadingState";
import { ErrorState } from "@/components/states/ErrorState";
import { EmptyState } from "@/components/states/EmptyState";
import { Table, Thead, Tbody, Tr, Th, Td } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatINR } from "@/lib/money";

export default function BrandCampaignsPage() {
  const q = useCampaigns({ page: 1, page_size: 50 });
  if (q.isLoading) return <LoadingState />;
  if (q.isError) return <ErrorState onRetry={() => q.refetch()} />;
  if (!q.data || q.data.items.length === 0) {
    return (
      <EmptyState
        title="No campaigns yet"
        description="Create your first campaign to start collaborating."
        action={
          <Link href="/brand/campaigns/new">
            <Button>New campaign</Button>
          </Link>
        }
      />
    );
  }
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Campaigns</h1>
        <Link href="/brand/campaigns/new">
          <Button>New campaign</Button>
        </Link>
      </div>
      <div className="rounded-md border border-slate-200 bg-white">
        <Table>
          <Thead>
            <Tr>
              <Th>Title</Th>
              <Th>Type</Th>
              <Th>Budget</Th>
              <Th>Status</Th>
              <Th></Th>
            </Tr>
          </Thead>
          <Tbody>
            {q.data.items.map((c) => (
              <Tr key={c.id}>
                <Td>{c.title}</Td>
                <Td>{c.type}</Td>
                <Td>{formatINR(c.budget_paise)}</Td>
                <Td>
                  <Badge>{c.status}</Badge>
                </Td>
                <Td className="text-right">
                  <Link
                    href={`/brand/campaigns/${c.id}`}
                    className="text-sm font-medium text-brand-600 underline"
                  >
                    Open
                  </Link>
                </Td>
              </Tr>
            ))}
          </Tbody>
        </Table>
      </div>
    </div>
  );
}
