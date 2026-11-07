"use client";

import Image from "next/image";
import { usePublicBrand } from "@/lib/api/queries";
import { ApiError, publicFileUrl } from "@/lib/api/client";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import { LoadingState } from "@/components/states/LoadingState";

function socialUrl(platform: string, value: string): string | null {
  if (/^https?:\/\//i.test(value)) return value;
  if (platform.toLowerCase() === "instagram") {
    return `https://www.instagram.com/${encodeURIComponent(value.replace(/^@+/, ""))}`;
  }
  return null;
}

export default function BrandPublicProfilePage({
  params,
}: {
  params: { id: string };
}) {
  const query = usePublicBrand(params.id);

  if (query.isLoading) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-10">
        <LoadingState label="Loading brand" />
      </main>
    );
  }
  if (query.isError) {
    if (query.error instanceof ApiError && query.error.status === 404) {
      return (
        <main className="mx-auto max-w-3xl px-6 py-10">
          <EmptyState
            title="Profile not public yet"
            description="This brand profile isn't public. If it's yours, add company name, industry, contact name and contact email, then save."
          />
        </main>
      );
    }
    return (
      <main className="mx-auto max-w-3xl px-6 py-10">
        <ErrorState
          description="This brand profile could not be loaded."
          onRetry={() => query.refetch()}
        />
      </main>
    );
  }
  const brand = query.data;
  if (!brand) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-10">
        <EmptyState title="Not found" description="This brand profile is not public." />
      </main>
    );
  }

  const socials = brand.social_handles ?? [];
  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 px-6 py-10">
      <header className="flex flex-wrap items-center gap-5">
        {brand.logo_file_id ? (
          <Image
            src={publicFileUrl(brand.logo_file_id)}
            alt={`${brand.company_name ?? "Brand"} logo`}
            width={112}
            height={112}
            unoptimized
            className="h-28 w-28 rounded-xl border border-slate-200 object-cover"
          />
        ) : null}
        <div className="flex flex-col gap-2">
          <h1 className="text-3xl font-bold">
            {brand.company_name ?? "Brand"}
          </h1>
          {brand.industry ? <Badge>{brand.industry}</Badge> : null}
          {[brand.city, brand.state].some(Boolean) ? (
            <p className="text-slate-600">
              {[brand.city, brand.state].filter(Boolean).join(", ")}
            </p>
          ) : null}
        </div>
      </header>

      {brand.description ? (
        <Card>
          <CardContent className="whitespace-pre-wrap py-5 text-sm text-slate-700">
            {brand.description}
          </CardContent>
        </Card>
      ) : null}

      {brand.website ? (
        <section>
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
            Website
          </h2>
          <a
            href={brand.website}
            target="_blank"
            rel="noreferrer noopener"
            className="break-all text-brand-600 underline"
          >
            {brand.website}
          </a>
        </section>
      ) : null}

      {socials.length ? (
        <section>
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
            Social profiles
          </h2>
          <ul className="flex flex-col gap-1 text-sm">
            {socials.map((social, index) => {
              const href = socialUrl(social.platform, social.handle);
              return (
                <li key={`${social.platform}-${index}`}>
                  <span className="font-medium">{social.platform}:</span>{" "}
                  {href ? (
                    <a
                      href={href}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="break-all text-brand-600 underline"
                    >
                      {social.handle}
                    </a>
                  ) : (
                    social.handle
                  )}
                  {social.unverified ? (
                    <Badge className="ml-2" tone="warning">
                      unverified
                    </Badge>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}
    </main>
  );
}
