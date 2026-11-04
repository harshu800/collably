"use client";

import { useCollaborations } from "@/lib/api/queries";
import { LoadingState } from "@/components/states/LoadingState";
import { ErrorState } from "@/components/states/ErrorState";
import { EmptyState } from "@/components/states/EmptyState";
import { Table, Thead, Tbody, Tr, Th, Td } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { formatINR } from "@/lib/money";

export default function CreatorHistoryPage() {
  const q = useCollaborations();
  if (q.isLoading) return <LoadingState />;
  if (q.isError) return <ErrorState onRetry={() => q.refetch()} />;
  const closed = (q.data ?? []).filter((c) =>
    ["completed", "cancelled"].includes(c.status),
  );
  if (closed.length === 0) {
    return (
      <EmptyState
        title="No closed collaborations"
        description="Completed and cancelled collaborations will show here."
      />
    );
  }
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold">History</h1>
      <div className="rounded-md border border-slate-200 bg-white">
        <Table>
          <Thead>
            <Tr>
              <Th>Status</Th>
              <Th>Amount</Th>
              <Th>Updated</Th>
            </Tr>
          </Thead>
          <Tbody>
            {closed.map((c) => (
              <Tr key={c.id}>
                <Td>
                  <Badge
                    tone={c.status === "completed" ? "success" : "neutral"}
                  >
                    {c.status}
                  </Badge>
                </Td>
                <Td>{formatINR(c.price_paise)}</Td>
                <Td>{new Date(c.updated_at).toLocaleDateString()}</Td>
              </Tr>
            ))}
          </Tbody>
        </Table>
      </div>
    </div>
  );
}
