"use client";

import { useAdminCampaigns, useArchiveCampaign } from "@/lib/api/queries";
import { LoadingState } from "@/components/states/LoadingState";
import { ErrorState } from "@/components/states/ErrorState";
import { EmptyState } from "@/components/states/EmptyState";
import { Table, Tbody, Td, Th, Thead, Tr } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatINR } from "@/lib/money";

export default function AdminCampaignsPage() {
  const q = useAdminCampaigns();
  const archive = useArchiveCampaign();
  if (q.isLoading) return <LoadingState />;
  if (q.isError) return <ErrorState onRetry={() => q.refetch()} />;
  if (!q.data || q.data.length === 0) {
    return <EmptyState title="No campaigns" />;
  }
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold">Campaigns</h1>
      <div className="rounded-md border border-slate-200 bg-white">
        <Table>
          <Thead>
            <Tr>
              <Th>Title</Th>
              <Th>Status</Th>
              <Th>Budget</Th>
              <Th></Th>
            </Tr>
          </Thead>
          <Tbody>
            {q.data.map((c) => (
              <Tr key={c.id}>
                <Td>{c.title}</Td>
                <Td>
                  <Badge>{c.status}</Badge>
                </Td>
                <Td>{formatINR(c.budget_paise)}</Td>
                <Td className="text-right">
                  {c.status !== "archived" ? (
                    <Button
                      size="sm"
                      variant="destructive"
                      disabled={archive.isPending}
                      onClick={() => archive.mutate(c.id)}
                    >
                      Archive
                    </Button>
                  ) : null}
                </Td>
              </Tr>
            ))}
          </Tbody>
        </Table>
      </div>
    </div>
  );
}
