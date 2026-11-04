"use client";

import * as React from "react";
import {
  useAgreement,
  useApproveDeliverable,
  useCollaboration,
  useDeliverables,
  useFunding,
  useInitiateFunding,
  useOpenDispute,
  usePayout,
  useRequestRevision,
  useSignAgreement,
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
import { Dialog, DialogFooter, DialogTitle } from "@/components/ui/dialog";
import { formatINR } from "@/lib/money";
import { useToast } from "@/components/ui/toast";

export default function BrandCollabDetailPage({
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
  const sign = useSignAgreement();
  const approve = useApproveDeliverable(id);
  const requestRev = useRequestRevision(id);
  const openDispute = useOpenDispute(id);
  const initFunding = useInitiateFunding();
  const { push } = useToast();

  const [revNote, setRevNote] = React.useState("");
  const [revFor, setRevFor] = React.useState<string | null>(null);
  const [disputeReason, setDisputeReason] = React.useState("");
  const [disputeOpen, setDisputeOpen] = React.useState(false);

  if (collab.isLoading || agreement.isLoading) return <LoadingState />;
  if (collab.isError) return <ErrorState onRetry={() => collab.refetch()} />;
  if (!collab.data) return <EmptyState title="Not found" />;

  const c = collab.data;
  const canFund =
    c.status === "agreement_signed" && c.funding_status === "not_funded";

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-bold">Collaboration workspace</h1>
        <div className="flex flex-wrap gap-1">
          <Badge>{c.status}</Badge>
          <Badge tone="info">Funding: {c.funding_status}</Badge>
          <Badge>Payout: {c.payout_status}</Badge>
          <Badge>{formatINR(c.price_paise)}</Badge>
        </div>
      </header>

      {payout.isError && (payout.error as { status?: number })?.status === 404 &&
      c.status === "approved" ? (
        <Alert tone="warning">
          Work is approved but no payout exists yet. The creator may not have
          set a payout method.
        </Alert>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Agreement</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {agreement.data ? (
            <>
              <p className="text-sm">
                Version {agreement.data.version_number} • Revision limit{" "}
                {agreement.data.revision_limit}
              </p>
              <p className="text-sm">
                You signed:{" "}
                {agreement.data.brand_signed_at ? "Yes" : "Not yet"}
              </p>
              <p className="text-sm">
                Creator signed:{" "}
                {agreement.data.creator_signed_at ? "Yes" : "Not yet"}
              </p>
              {!agreement.data.brand_signed_at ? (
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
          ) : (
            <EmptyState title="No agreement" />
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Funding</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {funding.isLoading ? (
            <LoadingState />
          ) : (
            <p className="text-sm">
              Status: <Badge tone="info">{funding.data?.funding_status}</Badge>
            </p>
          )}
          {canFund ? (
            <Button
              size="sm"
              disabled={initFunding.isPending}
              onClick={async () => {
                await initFunding.mutateAsync(id);
                push({ title: "Funding initiated", tone: "success" });
              }}
            >
              Initiate funding
            </Button>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Deliverables</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {deliverables.isLoading ? (
            <LoadingState />
          ) : (deliverables.data ?? []).length === 0 ? (
            <EmptyState title="No deliverables yet" />
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
                  {d.status === "submitted" ? (
                    <div className="mt-2 flex gap-2">
                      <Button
                        size="sm"
                        disabled={approve.isPending}
                        onClick={async () => {
                          await approve.mutateAsync(d.id);
                          push({ title: "Approved", tone: "success" });
                        }}
                      >
                        Approve
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => setRevFor(d.id)}
                      >
                        Request revision
                      </Button>
                    </div>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Dispute</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <p className="text-sm text-slate-600">
            Opening a dispute pauses the collaboration until an admin resolves
            it. Use this only after revision requests have failed.
          </p>
          <div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setDisputeOpen(true)}
            >
              Open dispute
            </Button>
          </div>
        </CardContent>
      </Card>

      <Dialog open={revFor !== null} onOpenChange={(o) => !o && setRevFor(null)}>
        <DialogTitle>Request a revision</DialogTitle>
        <Label htmlFor="rev-note" className="mt-3">
          Note
        </Label>
        <Textarea
          id="rev-note"
          rows={3}
          value={revNote}
          onChange={(e) => setRevNote(e.target.value)}
        />
        <DialogFooter>
          <Button variant="ghost" onClick={() => setRevFor(null)}>
            Cancel
          </Button>
          <Button
            disabled={!revFor || !revNote || requestRev.isPending}
            onClick={async () => {
              if (!revFor) return;
              await requestRev.mutateAsync({
                deliverableId: revFor,
                note: revNote,
              });
              setRevFor(null);
              setRevNote("");
              push({ title: "Revision requested", tone: "success" });
            }}
          >
            Send request
          </Button>
        </DialogFooter>
      </Dialog>

      <Dialog open={disputeOpen} onOpenChange={setDisputeOpen}>
        <DialogTitle>Open a dispute</DialogTitle>
        <Label htmlFor="dispute-reason" className="mt-3">
          Reason
        </Label>
        <Textarea
          id="dispute-reason"
          rows={4}
          value={disputeReason}
          onChange={(e) => setDisputeReason(e.target.value)}
        />
        <DialogFooter>
          <Button variant="ghost" onClick={() => setDisputeOpen(false)}>
            Cancel
          </Button>
          <Button
            disabled={!disputeReason || openDispute.isPending}
            onClick={async () => {
              await openDispute.mutateAsync(disputeReason);
              setDisputeOpen(false);
              setDisputeReason("");
              push({ title: "Dispute opened", tone: "info" });
            }}
          >
            Open dispute
          </Button>
        </DialogFooter>
      </Dialog>

      <Input
        aria-hidden
        className="hidden"
        tabIndex={-1}
        defaultValue=""
      />
    </div>
  );
}
