"use client";

import * as React from "react";
import { useAdminDisputes, useResolveDispute } from "@/lib/api/queries";
import { LoadingState } from "@/components/states/LoadingState";
import { ErrorState } from "@/components/states/ErrorState";
import { EmptyState } from "@/components/states/EmptyState";
import { Table, Tbody, Td, Th, Thead, Tr } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogFooter, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";

export default function AdminDisputesPage() {
  const q = useAdminDisputes();
  const resolve = useResolveDispute();
  const { push } = useToast();
  const [open, setOpen] = React.useState<string | null>(null);
  const [resolution, setResolution] = React.useState<
    "release_to_creator" | "refund_to_brand" | "split"
  >("release_to_creator");
  const [splitBps, setSplitBps] = React.useState("5000");

  if (q.isLoading) return <LoadingState />;
  if (q.isError) return <ErrorState onRetry={() => q.refetch()} />;
  if (!q.data || q.data.length === 0) {
    return <EmptyState title="No disputes" />;
  }
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold">Disputes</h1>
      <div className="rounded-md border border-slate-200 bg-white">
        <Table>
          <Thead>
            <Tr>
              <Th>Opened</Th>
              <Th>Collaboration</Th>
              <Th>Status</Th>
              <Th>Resolution</Th>
              <Th></Th>
            </Tr>
          </Thead>
          <Tbody>
            {q.data.map((d) => (
              <Tr key={d.id}>
                <Td>{new Date(d.created_at).toLocaleDateString()}</Td>
                <Td className="font-mono text-xs">
                  {d.collaboration_id.slice(0, 8)}…
                </Td>
                <Td>
                  <Badge>{d.status}</Badge>
                </Td>
                <Td>{d.resolution ?? "—"}</Td>
                <Td className="text-right">
                  {d.status === "open" ? (
                    <Button size="sm" onClick={() => setOpen(d.id)}>
                      Resolve
                    </Button>
                  ) : null}
                </Td>
              </Tr>
            ))}
          </Tbody>
        </Table>
      </div>
      <Dialog open={open !== null} onOpenChange={(o) => !o && setOpen(null)}>
        <DialogTitle>Resolve dispute</DialogTitle>
        <div className="mt-3 flex flex-col gap-3">
          <div>
            <Label htmlFor="resolution">Resolution</Label>
            <Select
              id="resolution"
              value={resolution}
              onChange={(e) =>
                setResolution(
                  e.target.value as
                    | "release_to_creator"
                    | "refund_to_brand"
                    | "split",
                )
              }
            >
              <option value="release_to_creator">
                Release payout to creator
              </option>
              <option value="refund_to_brand">Refund to brand</option>
              <option value="split">Split (bookkeeping only in v1)</option>
            </Select>
          </div>
          {resolution === "split" ? (
            <div>
              <Label htmlFor="split-bps">Split (basis points)</Label>
              <Input
                id="split-bps"
                type="number"
                min={0}
                max={10000}
                value={splitBps}
                onChange={(e) => setSplitBps(e.target.value)}
              />
              <p className="mt-1 text-xs text-slate-500">
                0..10000, where 10000 = 100%. v1 does not move money for a
                split — it records the share and completes the collaboration.
              </p>
            </div>
          ) : null}
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => setOpen(null)}>
            Cancel
          </Button>
          <Button
            disabled={!open || resolve.isPending}
            onClick={async () => {
              if (!open) return;
              await resolve.mutateAsync({
                id: open,
                resolution,
                split_bps:
                  resolution === "split"
                    ? Number.parseInt(splitBps, 10)
                    : undefined,
              });
              setOpen(null);
              push({ title: "Dispute resolved", tone: "success" });
            }}
          >
            Apply resolution
          </Button>
        </DialogFooter>
      </Dialog>
    </div>
  );
}
