"use client";

import type { ReactNode } from "react";
import { useMyProfile } from "@/lib/api/queries";
import { LoadingState } from "@/components/states/LoadingState";
import { ErrorState } from "@/components/states/ErrorState";
import { EmptyState } from "@/components/states/EmptyState";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { formatINR } from "@/lib/money";

function ProfileSection({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section>
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
        {title}
      </h2>
      {children}
    </section>
  );
}

export default function CreatorProfilePage() {
  const q = useMyProfile();
  if (q.isLoading) return <LoadingState />;
  if (q.isError)
    return (
      <ErrorState
        description="Could not load your profile."
        onRetry={() => q.refetch()}
      />
    );
  const p = q.data?.creator;
  if (!p) {
    return (
      <EmptyState
        title="No profile yet"
        description="Finish onboarding to set up your creator profile."
      />
    );
  }

  const location = [p.city, p.state].filter(Boolean).join(", ");

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-2xl font-bold">Your creator profile</h1>
        <p className="mt-1 text-sm text-slate-600">
          The details brands see when they discover your profile.
        </p>
      </header>
      <Card>
        <CardHeader>
          <CardTitle>{p.display_name || "Creator profile"}</CardTitle>
          <p className="text-sm text-slate-500">
            {location || "Location not added"}
          </p>
        </CardHeader>
        <CardContent className="flex flex-col gap-5">
          <div className="flex flex-wrap gap-2">
            {p.does_ugc ? <Badge tone="info">UGC creator</Badge> : null}
            {p.does_influencer ? (
              <Badge tone="info">Influencer</Badge>
            ) : null}
            {p.niches.map((niche) => (
              <Badge key={niche}>{niche}</Badge>
            ))}
            {!p.does_ugc && !p.does_influencer && p.niches.length === 0 ? (
              <span className="text-sm text-slate-500">
                Creator type and niches not added
              </span>
            ) : null}
          </div>
          {p.bio ? (
            <p className="whitespace-pre-wrap text-sm text-slate-700">{p.bio}</p>
          ) : null}
        </CardContent>
      </Card>
      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Starting rate</CardTitle>
          </CardHeader>
          <CardContent className="text-sm">
            {p.starting_rate_paise == null
              ? "Not added"
              : formatINR(p.starting_rate_paise)}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Languages</CardTitle>
          </CardHeader>
          <CardContent className="text-sm">
            {p.languages.length ? p.languages.join(", ") : "Not added"}
          </CardContent>
        </Card>
      </div>
      <ProfileSection title="Content types">
        <p className="text-sm text-slate-700">
          {p.content_types.length ? p.content_types.join(", ") : "Not added"}
        </p>
      </ProfileSection>
      <ProfileSection title="Portfolio">
        {p.portfolio_links.length ? (
          <ul className="flex flex-col gap-2 text-sm">
            {p.portfolio_links.map((link) => (
              <li key={link.url}>
                <a
                  href={link.url}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="text-brand-600 underline"
                >
                  {link.label}
                </a>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-slate-500">No portfolio links added</p>
        )}
      </ProfileSection>
      <ProfileSection title="Social profiles">
        {p.social_handles.length ? (
          <ul className="flex flex-col gap-2 text-sm text-slate-700">
            {p.social_handles.map((social) => (
              <li key={`${social.platform}-${social.handle}`}>
                <span className="font-medium">{social.platform}:</span>{" "}
                {social.handle}
                {social.follower_count != null
                  ? ` · ${social.follower_count.toLocaleString("en-IN")} followers`
                  : ""}
                {social.unverified ? (
                  <Badge className="ml-2" tone="warning">
                    Unverified
                  </Badge>
                ) : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-slate-500">No social profiles added</p>
        )}
      </ProfileSection>
    </div>
  );
}
