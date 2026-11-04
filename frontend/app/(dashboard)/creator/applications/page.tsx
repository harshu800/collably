"use client";

import { useMyApplications, useWithdrawApplication } from "@/lib/api/queries";
import { LoadingState } from "@/components/states/LoadingState";
import { ErrorState } from "@/components/states/ErrorState";
import { EmptyState } from "@/components/states/EmptyState";
import { Table, Thead, Tbody, Tr, Th, Td } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

export default function CreatorApplicationsPage() {
  const q = useMyApplications();
  const withdraw = useWithdrawApplication();
  if (q.isLoading) return <LoadingState />;
  if (q.isError)
    return (
      <ErrorState
        description="Could not load your applications."
        onRetry={() => q.refetch()}
      />
    );
  if (!q.data || q.data.length === 0) {
    return (
      <EmptyState
        title="No applications yet"
        description="Browse open campaigns and apply to get started."
      />
    );
  }
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold">My applications</h1>
      <div className="rounded-md border border-slate-200 bg-white">
        <Table>
          <Thead>
            <Tr>
              <Th>Submitted</Th>
              <Th>Status</Th>
              <Th>Campaign</Th>
              <Th></Th>
            </Tr>
          </Thead>
          <Tbody>
            {q.data.map((a) => (
              <Tr key={a.id}>
                <Td>{new Date(a.created_at).toLocaleDateString()}</Td>
                <Td>
                  <Badge tone={a.status === "accepted" ? "success" : "neutral"}>
                    {a.status}
                  </Badge>
                </Td>
                <Td className="font-mono text-xs text-slate-500">
                  {a.campaign_id.slice(0, 8)}…
                </Td>
                <Td className="text-right">
                  {["submitted", "shortlisted", "invited"].includes(
                    a.status,
                  ) ? (
                    <Button
                      variant="ghost"
                      size="sm"
                      disabled={withdraw.isPending}
                      onClick={() => withdraw.mutate(a.id)}
                    >
                      Withdraw
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
