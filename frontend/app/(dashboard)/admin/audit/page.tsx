"use client";

import { useAdminAuditLogs } from "@/lib/api/queries";
import { LoadingState } from "@/components/states/LoadingState";
import { ErrorState } from "@/components/states/ErrorState";
import { EmptyState } from "@/components/states/EmptyState";
import { Table, Tbody, Td, Th, Thead, Tr } from "@/components/ui/table";

export default function AdminAuditPage() {
  const q = useAdminAuditLogs();
  if (q.isLoading) return <LoadingState />;
  if (q.isError) return <ErrorState onRetry={() => q.refetch()} />;
  if (!q.data || q.data.length === 0) {
    return <EmptyState title="No audit entries yet" />;
  }
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold">Audit log</h1>
      <div className="rounded-md border border-slate-200 bg-white">
        <Table>
          <Thead>
            <Tr>
              <Th>When</Th>
              <Th>Action</Th>
              <Th>Target</Th>
              <Th>Actor</Th>
              <Th>Diff</Th>
            </Tr>
          </Thead>
          <Tbody>
            {q.data.map((a) => (
              <Tr key={a.id}>
                <Td>{new Date(a.occurred_at).toLocaleString()}</Td>
                <Td className="font-mono text-xs">{a.action}</Td>
                <Td className="font-mono text-xs">
                  {a.target_type}
                  {a.target_id ? `:${a.target_id.slice(0, 8)}…` : ""}
                </Td>
                <Td className="font-mono text-xs">
                  {a.actor_user_id ? a.actor_user_id.slice(0, 8) + "…" : "system"}
                </Td>
                <Td>
                  <pre className="whitespace-pre-wrap text-xs text-slate-600">
                    {JSON.stringify(a.diff, null, 2)}
                  </pre>
                </Td>
              </Tr>
            ))}
          </Tbody>
        </Table>
      </div>
    </div>
  );
}
