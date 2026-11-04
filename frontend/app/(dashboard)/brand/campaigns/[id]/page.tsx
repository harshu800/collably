"use client";

import {
  useAcceptApplication,
  useCampaign,
  useCampaignApplications,
  useRejectApplication,
} from "@/lib/api/queries";
import { LoadingState } from "@/components/states/LoadingState";
import { ErrorState } from "@/components/states/ErrorState";
import { EmptyState } from "@/components/states/EmptyState";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, Tbody, Td, Th, Thead, Tr } from "@/components/ui/table";
import { formatINR } from "@/lib/money";
import { useToast } from "@/components/ui/toast";

export default function BrandCampaignDetailPage({
  params,
}: {
  params: { id: string };
}) {
  const campaign = useCampaign(params.id);
  const apps = useCampaignApplications(params.id);
  const accept = useAcceptApplication();
  const reject = useRejectApplication();
  const { push } = useToast();

  if (campaign.isLoading) return <LoadingState />;
  if (campaign.isError)
    return <ErrorState onRetry={() => campaign.refetch()} />;
  if (!campaign.data) return <EmptyState title="Not found" />;

  const c = campaign.data;
  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-bold">{c.title}</h1>
        <div className="flex flex-wrap gap-1">
          <Badge>{c.status}</Badge>
          <Badge tone="info">{c.type}</Badge>
          <Badge>{formatINR(c.budget_paise)}</Badge>
        </div>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Applications</CardTitle>
        </CardHeader>
        <CardContent>
          {apps.isLoading ? (
            <LoadingState />
          ) : apps.isError ? (
            <ErrorState onRetry={() => apps.refetch()} />
          ) : (apps.data ?? []).length === 0 ? (
            <EmptyState title="No applications yet" />
          ) : (
            <Table>
              <Thead>
                <Tr>
                  <Th>Creator</Th>
                  <Th>Status</Th>
                  <Th></Th>
                </Tr>
              </Thead>
              <Tbody>
                {(apps.data ?? []).map((a) => (
                  <Tr key={a.id}>
                    <Td className="font-mono text-xs">{a.creator_id.slice(0, 8)}…</Td>
                    <Td>
                      <Badge>{a.status}</Badge>
                    </Td>
                    <Td className="flex justify-end gap-2">
                      {["submitted", "shortlisted", "invited"].includes(
                        a.status,
                      ) ? (
                        <>
                          <Button
                            size="sm"
                            disabled={accept.isPending}
                            onClick={async () => {
                              const r = await accept.mutateAsync(a.id);
                              push({
                                title: "Accepted",
                                description: `Collaboration ${r.collaboration_id.slice(0, 8)}…`,
                                tone: "success",
                              });
                            }}
                          >
                            Accept
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            disabled={reject.isPending}
                            onClick={() => reject.mutate(a.id)}
                          >
                            Reject
                          </Button>
                        </>
                      ) : null}
                    </Td>
                  </Tr>
                ))}
              </Tbody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
