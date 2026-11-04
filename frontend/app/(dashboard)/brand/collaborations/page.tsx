"use client";

import Link from "next/link";
import { useCollaborations } from "@/lib/api/queries";
import { LoadingState } from "@/components/states/LoadingState";
import { ErrorState } from "@/components/states/ErrorState";
import { EmptyState } from "@/components/states/EmptyState";
import { Table, Thead, Tbody, Tr, Th, Td } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { formatINR } from "@/lib/money";

export default function BrandCollaborationsPage() {
  const q = useCollaborations();
  if (q.isLoading) return <LoadingState />;
  if (q.isError) return <ErrorState onRetry={() => q.refetch()} />;
  const open =
    (q.data ?? []).filter(
      (c) => !["completed", "cancelled"].includes(c.status),
    );
  if (open.length === 0) {
    return (
      <EmptyState
        title="No active collaborations"
        description="Accept an application to start a collaboration."
      />
    );
  }
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold">Active collaborations</h1>
      <div className="rounded-md border border-slate-200 bg-white">
        <Table>
          <Thead>
            <Tr>
              <Th>Status</Th>
              <Th>Funding</Th>
              <Th>Payout</Th>
              <Th>Amount</Th>
              <Th></Th>
            </Tr>
          </Thead>
          <Tbody>
            {open.map((c) => (
              <Tr key={c.id}>
                <Td>
                  <Badge>{c.status}</Badge>
                </Td>
                <Td>{c.funding_status}</Td>
                <Td>{c.payout_status}</Td>
                <Td>{formatINR(c.price_paise)}</Td>
                <Td className="text-right">
                  <Link
                    href={`/brand/collaborations/${c.id}`}
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
