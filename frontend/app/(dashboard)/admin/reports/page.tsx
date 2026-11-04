"use client";

import { useAdminReports, useReviewReport } from "@/lib/api/queries";
import { LoadingState } from "@/components/states/LoadingState";
import { ErrorState } from "@/components/states/ErrorState";
import { EmptyState } from "@/components/states/EmptyState";
import { Table, Tbody, Td, Th, Thead, Tr } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";

export default function AdminReportsPage() {
  const q = useAdminReports();
  const review = useReviewReport();
  const { push } = useToast();
  if (q.isLoading) return <LoadingState />;
  if (q.isError) return <ErrorState onRetry={() => q.refetch()} />;
  if (!q.data || q.data.length === 0) {
    return <EmptyState title="No reports" description="Nothing has been flagged." />;
  }
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold">Reports</h1>
      <div className="rounded-md border border-slate-200 bg-white">
        <Table>
          <Thead>
            <Tr>
              <Th>Target</Th>
              <Th>Reason</Th>
              <Th>Status</Th>
              <Th></Th>
            </Tr>
          </Thead>
          <Tbody>
            {q.data.map((r) => (
              <Tr key={r.id}>
                <Td className="font-mono text-xs">
                  {r.target_type}:{r.target_id.slice(0, 8)}…
                </Td>
                <Td className="max-w-md truncate">{r.reason}</Td>
                <Td>
                  <Badge>{r.status}</Badge>
                </Td>
                <Td className="flex justify-end gap-2">
                  {r.status === "open" ? (
                    <>
                      <Button
                        size="sm"
                        disabled={review.isPending}
                        onClick={async () => {
                          await review.mutateAsync({
                            id: r.id,
                            status: "reviewed",
                          });
                          push({ title: "Marked reviewed", tone: "success" });
                        }}
                      >
                        Mark reviewed
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={review.isPending}
                        onClick={async () => {
                          await review.mutateAsync({
                            id: r.id,
                            status: "dismissed",
                          });
                          push({ title: "Dismissed", tone: "info" });
                        }}
                      >
                        Dismiss
                      </Button>
                    </>
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
