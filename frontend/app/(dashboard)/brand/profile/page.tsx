"use client";

import { useMyProfile } from "@/lib/api/queries";
import { LoadingState } from "@/components/states/LoadingState";
import { ErrorState } from "@/components/states/ErrorState";
import { EmptyState } from "@/components/states/EmptyState";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export default function BrandProfilePage() {
  const q = useMyProfile();
  if (q.isLoading) return <LoadingState />;
  if (q.isError)
    return <ErrorState onRetry={() => q.refetch()} />;
  const b = q.data?.brand;
  if (!b) {
    return (
      <EmptyState
        title="No brand profile yet"
        description="Finish onboarding to set up your company details."
      />
    );
  }

  const address = b.billing_address;
  const billingAddress = [
    address.line1,
    address.line2,
    address.city,
    address.state,
    address.postal_code,
    address.country,
  ]
    .filter(Boolean)
    .join(", ");

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-2xl font-bold">Brand profile</h1>
        <p className="mt-1 text-sm text-slate-600">
          Your company details for creator collaborations.
        </p>
      </header>
      <Card>
        <CardHeader>
          <CardTitle>{b.company_name || "Company profile"}</CardTitle>
          {b.industry ? (
            <p className="text-sm text-slate-500">{b.industry}</p>
          ) : null}
        </CardHeader>
        <CardContent className="flex flex-col gap-5">
          {b.description ? (
            <p className="whitespace-pre-wrap text-sm text-slate-700">
              {b.description}
            </p>
          ) : null}
          <dl className="grid gap-4 text-sm sm:grid-cols-2">
            <div>
              <dt className="font-medium text-slate-500">Contact name</dt>
              <dd className="mt-1 text-slate-900">
                {b.contact_name || "Not added"}
              </dd>
            </div>
            <div>
              <dt className="font-medium text-slate-500">Contact email</dt>
              <dd className="mt-1 text-slate-900">
                {b.contact_email ? (
                  <a
                    className="text-brand-600 underline"
                    href={`mailto:${b.contact_email}`}
                  >
                    {b.contact_email}
                  </a>
                ) : (
                  "Not added"
                )}
              </dd>
            </div>
            <div>
              <dt className="font-medium text-slate-500">Website</dt>
              <dd className="mt-1 break-all text-slate-900">
                {b.website ? (
                  <a
                    className="text-brand-600 underline"
                    href={b.website}
                    target="_blank"
                    rel="noreferrer noopener"
                  >
                    {b.website}
                  </a>
                ) : (
                  "Not added"
                )}
              </dd>
            </div>
            <div>
              <dt className="font-medium text-slate-500">GSTIN</dt>
              <dd className="mt-1 text-slate-900">{b.gstin || "Not added"}</dd>
            </div>
          </dl>
        </CardContent>
      </Card>
      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
          Billing address
        </h2>
        <p className="whitespace-pre-wrap text-sm text-slate-700">
          {billingAddress || "Not added"}
        </p>
      </section>
    </div>
  );
}
