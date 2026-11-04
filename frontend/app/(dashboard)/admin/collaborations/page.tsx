"use client";

import { useAdminCollaborations } from "@/lib/api/queries";
import { LoadingState } from "@/components/states/LoadingState";
import { ErrorState } from "@/components/states/ErrorState";
import { EmptyState } from "@/components/states/EmptyState";
import { Table, Tbody, Td, Th, Thead, Tr } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { formatINR } from "@/lib/money";

export default function AdminCollaborationsPage() {
  const q = useAdminCollaborations();
  if (q.isLoading) return <LoadingState />;
  if (q.isError) return <ErrorState onRetry={() => q.refetch()} />;
  if (!q.data || q.data.length === 0) {
    return <EmptyState title="No collaborations" />;
  }
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold">Collaborations</h1>
      <div className="rounded-md border border-slate-200 bg-white">
        <Table>
          <Thead>
            <Tr>
              <Th>Status</Th>
              <Th>Funding</Th>
              <Th>Payout</Th>
              <Th>Amount</Th>
            </Tr>
          </Thead>
          <Tbody>
            {q.data.map((c) => (
              <Tr key={c.id}>
                <Td>
                  <Badge>{c.status}</Badge>
                </Td>
                <Td>{c.funding_status}</Td>
                <Td>{c.payout_status}</Td>
                <Td>{formatINR(c.price_paise)}</Td>
              </Tr>
            ))}
          </Tbody>
        </Table>
      </div>
    </div>
  );
}
