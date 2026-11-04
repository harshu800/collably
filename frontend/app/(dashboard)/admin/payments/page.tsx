"use client";

import { useAdminPaymentEvents } from "@/lib/api/queries";
import { LoadingState } from "@/components/states/LoadingState";
import { ErrorState } from "@/components/states/ErrorState";
import { EmptyState } from "@/components/states/EmptyState";
import { Table, Tbody, Td, Th, Thead, Tr } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";

export default function AdminPaymentsPage() {
  const q = useAdminPaymentEvents();
  if (q.isLoading) return <LoadingState />;
  if (q.isError) return <ErrorState onRetry={() => q.refetch()} />;
  if (!q.data || q.data.length === 0) {
    return <EmptyState title="No payment events" />;
  }
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold">Payment webhook events</h1>
      <p className="text-sm text-slate-600">
        Read-only. These are the verified webhook deliveries from the payment
        provider.
      </p>
      <div className="rounded-md border border-slate-200 bg-white">
        <Table>
          <Thead>
            <Tr>
              <Th>Provider</Th>
              <Th>Event id</Th>
              <Th>Type</Th>
              <Th>Verified</Th>
              <Th>Processed</Th>
            </Tr>
          </Thead>
          <Tbody>
            {q.data.map((e) => (
              <Tr key={e.id}>
                <Td>{e.provider}</Td>
                <Td className="font-mono text-xs">
                  {e.provider_event_id.slice(0, 12)}…
                </Td>
                <Td>{e.event_type}</Td>
                <Td>
                  <Badge tone={e.verified ? "success" : "danger"}>
                    {e.verified ? "yes" : "no"}
                  </Badge>
                </Td>
                <Td>{e.processed_at ? "yes" : "pending"}</Td>
              </Tr>
            ))}
          </Tbody>
        </Table>
      </div>
    </div>
  );
}
