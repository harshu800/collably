"use client";

import { useAdminUsers, useDeactivateUser } from "@/lib/api/queries";
import { LoadingState } from "@/components/states/LoadingState";
import { ErrorState } from "@/components/states/ErrorState";
import { EmptyState } from "@/components/states/EmptyState";
import { Table, Tbody, Td, Th, Thead, Tr } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";

export default function AdminUsersPage() {
  const q = useAdminUsers();
  const deactivate = useDeactivateUser();
  const { push } = useToast();
  if (q.isLoading) return <LoadingState />;
  if (q.isError) return <ErrorState onRetry={() => q.refetch()} />;
  if (!q.data || q.data.length === 0) {
    return <EmptyState title="No users yet" />;
  }
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold">Users</h1>
      <div className="rounded-md border border-slate-200 bg-white">
        <Table>
          <Thead>
            <Tr>
              <Th>Email</Th>
              <Th>Role</Th>
              <Th>Active</Th>
              <Th>Created</Th>
              <Th></Th>
            </Tr>
          </Thead>
          <Tbody>
            {q.data.map((u) => (
              <Tr key={u.id}>
                <Td>{u.email}</Td>
                <Td>
                  <Badge>{u.role}</Badge>
                </Td>
                <Td>
                  {u.is_active ? (
                    <Badge tone="success">active</Badge>
                  ) : (
                    <Badge tone="danger">inactive</Badge>
                  )}
                </Td>
                <Td>{new Date(u.created_at).toLocaleDateString()}</Td>
                <Td className="text-right">
                  {u.is_active ? (
                    <Button
                      size="sm"
                      variant="destructive"
                      disabled={deactivate.isPending}
                      onClick={async () => {
                        await deactivate.mutateAsync(u.id);
                        push({ title: "User deactivated", tone: "info" });
                      }}
                    >
                      Deactivate
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
