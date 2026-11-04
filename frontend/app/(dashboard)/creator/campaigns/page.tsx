"use client";

import Link from "next/link";
import { useCampaigns, useSubmitApplication } from "@/lib/api/queries";
import { LoadingState } from "@/components/states/LoadingState";
import { ErrorState } from "@/components/states/ErrorState";
import { EmptyState } from "@/components/states/EmptyState";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { formatINR } from "@/lib/money";
import { useToast } from "@/components/ui/toast";

export default function CreatorCampaignsPage() {
  const q = useCampaigns({ page: 1, page_size: 30 });
  const { push } = useToast();
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold">Browse campaigns</h1>
      {q.isLoading ? (
        <LoadingState />
      ) : q.isError ? (
        <ErrorState onRetry={() => q.refetch()} />
      ) : !q.data || q.data.items.length === 0 ? (
        <EmptyState title="No campaigns open" description="Check again soon." />
      ) : (
        <ul className="grid gap-3 md:grid-cols-2">
          {q.data.items.map((c) => (
            <li key={c.id}>
              <CampaignRow
                campaignId={c.id}
                title={c.title}
                budget={c.budget_paise}
                type={c.type}
                niches={c.niches}
                onApplied={() =>
                  push({
                    title: "Application sent",
                    description: c.title,
                    tone: "success",
                  })
                }
              />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function CampaignRow({
  campaignId,
  title,
  budget,
  type,
  niches,
  onApplied,
}: {
  campaignId: string;
  title: string;
  budget: number;
  type: string;
  niches: string[];
  onApplied: () => void;
}) {
  const apply = useSubmitApplication(campaignId);
  return (
    <Card>
      <CardContent className="flex flex-col gap-2">
        <Link href={`/campaigns/${campaignId}`} className="text-base font-semibold text-slate-900 hover:underline">
          {title}
        </Link>
        <p className="text-sm text-slate-600">
          {formatINR(budget)} • {type}
        </p>
        <div className="flex flex-wrap gap-1">
          {niches.slice(0, 3).map((n) => (
            <Badge key={n}>{n}</Badge>
          ))}
        </div>
        <Button
          size="sm"
          disabled={apply.isPending}
          onClick={async () => {
            try {
              await apply.mutateAsync({ pitch: "I would like to apply." });
              onApplied();
            } catch {
              /* surfaced inline via toast if needed */
            }
          }}
        >
          {apply.isPending ? "Applying…" : "Apply"}
        </Button>
      </CardContent>
    </Card>
  );
}
