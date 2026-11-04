"use client";

import * as React from "react";
import {
  useAgreement,
  useCollaboration,
  useCreatePayout,
  useDeliverables,
  useFunding,
  usePayout,
  useSignAgreement,
  useSubmitDeliverable,
} from "@/lib/api/queries";
import { LoadingState } from "@/components/states/LoadingState";
import { ErrorState } from "@/components/states/ErrorState";
import { EmptyState } from "@/components/states/EmptyState";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/alert";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { formatINR } from "@/lib/money";
import { useToast } from "@/components/ui/toast";

export default function CreatorCollabDetailPage({
  params,
}: {
  params: { id: string };
}) {
  const id = params.id;
  const collab = useCollaboration(id);
  const agreement = useAgreement(id);
  const deliverables = useDeliverables(id);
  const funding = useFunding(id);
  const payout = usePayout(id);
  const submit = useSubmitDeliverable(id);
  const sign = useSignAgreement();
  const createPayout = useCreatePayout();
  const { push } = useToast();

  const [specIndex, setSpecIndex] = React.useState("0");
  const [url, setUrl] = React.useState("");
  const [caption, setCaption] = React.useState("");

  if (collab.isLoading || agreement.isLoading) return <LoadingState />;
  if (collab.isError)
    return <ErrorState onRetry={() => collab.refetch()} />;
  if (!collab.data) return <EmptyState title="Not found" />;

  const canSubmit =
    collab.data.funding_status === "funding_confirmed" &&
    agreement.data?.brand_signed_at &&
    agreement.data?.creator_signed_at;

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-bold">Collaboration</h1>
        <div className="flex flex-wrap gap-1">
          <Badge>{collab.data.status}</Badge>
          <Badge tone="info">Funding: {collab.data.funding_status}</Badge>
          <Badge>Payout: {collab.data.payout_status}</Badge>
          <Badge>{formatINR(collab.data.price_paise)}</Badge>
        </div>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Agreement</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {agreement.isError ? (
            <ErrorState description="Could not load the current agreement." />
          ) : agreement.data ? (
            <>
              <p className="text-sm">
                Version {agreement.data.version_number} • Revision limit{" "}
                {agreement.data.revision_limit}
              </p>
              <p className="text-sm">
                Brand signed:{" "}
                {agreement.data.brand_signed_at ? "Yes" : "Not yet"}
              </p>
              <p className="text-sm">
                You signed:{" "}
                {agreement.data.creator_signed_at ? "Yes" : "Not yet"}
              </p>
              {!agreement.data.creator_signed_at ? (
                <Button
                  size="sm"
                  disabled={sign.isPending}
                  onClick={async () => {
                    await sign.mutateAsync(agreement.data!.id);
                    push({ title: "Agreement signed", tone: "success" });
                  }}
                >
                  Sign agreement
                </Button>
              ) : null}
            </>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Funding</CardTitle>
        </CardHeader>
        <CardContent>
          {funding.isLoading ? (
            <LoadingState />
          ) : funding.isError ? (
            <ErrorState onRetry={() => funding.refetch()} />
          ) : (
            <p className="text-sm">
              Status: <Badge tone="info">{funding.data?.funding_status}</Badge>
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Deliverables</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {deliverables.isLoading ? (
            <LoadingState />
          ) : deliverables.isError ? (
            <ErrorState onRetry={() => deliverables.refetch()} />
          ) : (deliverables.data ?? []).length === 0 ? (
            <EmptyState title="No deliverables submitted yet" />
          ) : (
            <ul className="flex flex-col gap-2">
              {(deliverables.data ?? []).map((d) => (
                <li
                  key={d.id}
                  className="rounded border border-slate-200 p-3 text-sm"
                >
                  <div className="flex items-center justify-between">
                    <span>Item {d.spec_index + 1}</span>
                    <Badge
                      tone={
                        d.status === "approved"
                          ? "success"
                          : d.status === "revision_requested"
                          ? "warning"
                          : "neutral"
                      }
                    >
                      {d.status}
                    </Badge>
                  </div>
                  {d.external_url ? (
                    <a
                      href={d.external_url}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="text-brand-600 underline"
                    >
                      {d.external_url}
                    </a>
                  ) : null}
                  {d.caption ? (
                    <p className="mt-1 text-slate-600">{d.caption}</p>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
          {canSubmit ? (
            <form
              className="flex flex-col gap-2 border-t border-slate-200 pt-4"
              onSubmit={async (e) => {
                e.preventDefault();
                try {
                  await submit.mutateAsync({
                    spec_index: Number.parseInt(specIndex, 10) || 0,
                    kind: "link",
                    external_url: url,
                    caption: caption || undefined,
                  });
                  setUrl("");
                  setCaption("");
                  push({ title: "Deliverable submitted", tone: "success" });
                } catch (err) {
                  push({
                    title: "Could not submit",
                    description: err instanceof Error ? err.message : "",
                    tone: "error",
                  });
                }
              }}
            >
              <Label htmlFor="dlv-url">Deliverable URL</Label>
              <Input
                id="dlv-url"
                type="url"
                required
                value={url}
                onChange={(e) => setUrl(e.target.value)}
              />
              <Label htmlFor="dlv-caption">Caption (optional)</Label>
              <Textarea
                id="dlv-caption"
                rows={2}
                value={caption}
                onChange={(e) => setCaption(e.target.value)}
              />
              <Label htmlFor="dlv-spec">Spec index</Label>
              <Input
                id="dlv-spec"
                type="number"
                min={0}
                value={specIndex}
                onChange={(e) => setSpecIndex(e.target.value)}
              />
              <Button type="submit" disabled={submit.isPending} size="sm">
                {submit.isPending ? "Submitting…" : "Submit deliverable"}
              </Button>
            </form>
          ) : (
            <Alert tone="info">
              You can submit once both parties sign and funding is confirmed.
            </Alert>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Payout</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-2">
          {payout.isError && (payout.error as { status?: number })?.status !== 404 ? (
            <ErrorState onRetry={() => payout.refetch()} />
          ) : payout.data ? (
            <p className="text-sm">
              Status: <Badge>{payout.data.status}</Badge> • Amount{" "}
              {formatINR(payout.data.amount_paise)}
            </p>
          ) : (
            <>
              <p className="text-sm text-slate-600">
                No payout yet. Once every spec item is approved, you can
                request the payout.
              </p>
              {collab.data.status === "approved" ? (
                <Button
                  size="sm"
                  disabled={createPayout.isPending}
                  onClick={() => createPayout.mutate(id)}
                >
                  {createPayout.isPending ? "Requesting…" : "Request payout"}
                </Button>
              ) : null}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
