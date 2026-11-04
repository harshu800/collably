"use client";

import Link from "next/link";
import { useCollaborations } from "@/lib/api/queries";
import { LoadingState } from "@/components/states/LoadingState";
import { ErrorState } from "@/components/states/ErrorState";
import { EmptyState } from "@/components/states/EmptyState";
import { Table, Thead, Tbody, Tr, Th, Td } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { formatINR } from "@/lib/money";

export default function CreatorPaymentsPage() {
  const q = useCollaborations();
  if (q.isLoading) return <LoadingState />;
  if (q.isError) return <ErrorState onRetry={() => q.refetch()} />;
  const rows = q.data ?? [];
  if (rows.length === 0) {
    return (
      <EmptyState
        title="No payments yet"
        description="Payment and payout history will show here once collaborations fund."
      />
    );
  }
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold">Payments</h1>
      <div className="rounded-md border border-slate-200 bg-white">
        <Table>
          <Thead>
            <Tr>
              <Th>Amount</Th>
              <Th>Funding</Th>
              <Th>Payout</Th>
              <Th>Status</Th>
              <Th></Th>
            </Tr>
          </Thead>
          <Tbody>
            {rows.map((c) => (
              <Tr key={c.id}>
                <Td>{formatINR(c.price_paise)}</Td>
                <Td>
                  <Badge tone="info">{c.funding_status}</Badge>
                </Td>
                <Td>
                  <Badge>{c.payout_status}</Badge>
                </Td>
                <Td>{c.status}</Td>
                <Td className="text-right">
                  <Link
                    href={`/creator/collaborations/${c.id}`}
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
