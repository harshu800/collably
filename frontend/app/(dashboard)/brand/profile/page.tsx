"use client";

import * as React from "react";
import Link from "next/link";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { ErrorState } from "@/components/states/ErrorState";
import { EmptyState } from "@/components/states/EmptyState";
import { LoadingState } from "@/components/states/LoadingState";
import { ProfileImageUpload } from "@/components/forms/ProfileImageUpload";
import { useMyProfile, useUpdateProfile } from "@/lib/api/queries";
import { normalizeSocialHandles } from "@/lib/profile-socials";
import type { BrandProfileSelf } from "@/lib/api/types";

function BrandProfileEditor({ profile }: { profile: BrandProfileSelf }) {
  const updateProfile = useUpdateProfile();
  const [logoFileId, setLogoFileId] = React.useState(profile.logo_file_id);
  const [companyName, setCompanyName] = React.useState(profile.company_name ?? "");
  const [industry, setIndustry] = React.useState(profile.industry ?? "");
  const [brandCity, setBrandCity] = React.useState(profile.city ?? "");
  const [brandState, setBrandState] = React.useState(profile.state ?? "");
  const [website, setWebsite] = React.useState(profile.website ?? "");
  const [contactName, setContactName] = React.useState(profile.contact_name ?? "");
  const [contactEmail, setContactEmail] = React.useState(profile.contact_email ?? "");
  const [gstin, setGstin] = React.useState(profile.gstin ?? "");
  const [description, setDescription] = React.useState(profile.description ?? "");
  const [instagram, setInstagram] = React.useState(
    profile.social_handles?.find(
      (item) => item.platform.toLowerCase() === "instagram",
    )?.handle ?? "",
  );
  const [instagramMetadata, setInstagramMetadata] = React.useState(
    profile.social_handles?.find(
      (item) => item.platform.toLowerCase() === "instagram",
    ),
  );
  const [otherSocials, setOtherSocials] = React.useState(
    (profile.social_handles ?? []).filter(
      (item) => item.platform.toLowerCase() !== "instagram",
    ),
  );
  const [newSocialPlatform, setNewSocialPlatform] = React.useState("");
  const [newSocialHandle, setNewSocialHandle] = React.useState("");
  const [uploadingLogo, setUploadingLogo] = React.useState(false);
  const [line1, setLine1] = React.useState(profile.billing_address.line1 ?? "");
  const [line2, setLine2] = React.useState(profile.billing_address.line2 ?? "");
  const [city, setCity] = React.useState(profile.billing_address.city ?? "");
  const [state, setState] = React.useState(profile.billing_address.state ?? "");
  const [postalCode, setPostalCode] = React.useState(
    profile.billing_address.postal_code ?? "",
  );
  const [country, setCountry] = React.useState(
    profile.billing_address.country ?? "IN",
  );
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [saved, setSaved] = React.useState(false);

  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSaved(false);
    const addressFields = [line1, city, state, postalCode];
    const hasAddress = [line1, line2, city, state, postalCode].some((value) =>
      value.trim(),
    );
    if (hasAddress && addressFields.some((value) => !value.trim())) {
      setError(
        "Complete address line, city, state, and postal code, or clear the address fields.",
      );
      return;
    }

    setSaving(true);
    try {
      await updateProfile.mutateAsync({
        logo_file_id: logoFileId,
        company_name: companyName.trim() || null,
        industry: industry.trim() || null,
        city: brandCity.trim() || null,
        state: brandState.trim() || null,
        website: website.trim() || null,
        contact_name: contactName.trim() || null,
        contact_email: contactEmail.trim() || null,
        gstin: gstin.trim() || null,
        description: description.trim() || null,
        social_handles: normalizeSocialHandles([
          ...otherSocials,
          ...(instagram.trim()
            ? [
                {
                  platform: "Instagram",
                  handle: `@${instagram.trim().replace(/^@+/, "")}`,
                  follower_count: instagramMetadata?.follower_count,
                  unverified: instagramMetadata?.unverified ?? true,
                },
              ]
            : []),
        ]),
        ...(hasAddress
          ? {
              billing_address: {
                line1: line1.trim(),
                line2: line2.trim() || null,
                city: city.trim(),
                state: state.trim(),
                postal_code: postalCode.trim(),
                country: country.trim().toUpperCase() || "IN",
              },
            }
          : {}),
      });
      setSaved(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save your profile.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="flex flex-col gap-6" onSubmit={save}>
      <header>
        <h1 className="text-2xl font-bold">Brand profile</h1>
        <p className="mt-1 text-sm text-slate-600">
          Add your company logo and details for creator collaborations. Save
          changes to publish your logo and profile edits.
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Company logo</CardTitle>
        </CardHeader>
        <CardContent>
          <ProfileImageUpload
            fileId={logoFileId}
            onChange={setLogoFileId}
            onUploadingChange={setUploadingLogo}
            label="company logo"
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Company details</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <label className="flex flex-col gap-1 text-sm font-medium">
            Company name
            <Input
              maxLength={200}
              value={companyName}
              onChange={(event) => setCompanyName(event.target.value)}
              placeholder="Your company"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium">
            Industry
            <Input
              maxLength={120}
              value={industry}
              onChange={(event) => setIndustry(event.target.value)}
              placeholder="e.g. Beauty"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium">
            Company city
            <Input
              maxLength={120}
              value={brandCity}
              onChange={(event) => setBrandCity(event.target.value)}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium">
            Company state
            <Input
              maxLength={120}
              value={brandState}
              onChange={(event) => setBrandState(event.target.value)}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium">
            Website
            <Input
              type="url"
              maxLength={2048}
              value={website}
              onChange={(event) => setWebsite(event.target.value)}
              placeholder="https://example.com"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium">
            GSTIN
            <Input
              maxLength={15}
              value={gstin}
              onChange={(event) => setGstin(event.target.value.toUpperCase())}
              placeholder="15-character GSTIN"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium">
            Contact name
            <Input
              maxLength={200}
              value={contactName}
              onChange={(event) => setContactName(event.target.value)}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium">
            Contact email
            <Input
              type="email"
              maxLength={320}
              value={contactEmail}
              onChange={(event) => setContactEmail(event.target.value)}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium sm:col-span-2">
            Company description
            <Textarea
              maxLength={2000}
              rows={4}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Tell creators about your company"
            />
          </label>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Public social profiles</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <label className="flex max-w-xl flex-col gap-1 text-sm font-medium">
            Instagram handle
            <Input
              value={instagram}
              onChange={(event) => setInstagram(event.target.value)}
              placeholder="@yourbrand"
              maxLength={120}
            />
          </label>
          {otherSocials.map((social, index) => (
            <div
              key={`${social.platform}-${index}`}
              className="grid gap-2 sm:grid-cols-[1fr_2fr_auto]"
            >
              <Input
                aria-label={`Brand social platform ${index + 1}`}
                value={social.platform}
                maxLength={50}
                onChange={(event) =>
                  setOtherSocials((current) =>
                    current.map((item, currentIndex) =>
                      currentIndex === index
                        ? { ...item, platform: event.target.value }
                        : item,
                    ),
                  )
                }
              />
              <Input
                aria-label={`Brand social profile ${index + 1}`}
                value={social.handle}
                maxLength={2048}
                onChange={(event) =>
                  setOtherSocials((current) =>
                    current.map((item, currentIndex) =>
                      currentIndex === index
                        ? { ...item, handle: event.target.value }
                        : item,
                    ),
                  )
                }
              />
              <Button
                type="button"
                variant="ghost"
                onClick={() =>
                  setOtherSocials((current) =>
                    current.filter((_, currentIndex) => currentIndex !== index),
                  )
                }
              >
                Remove
              </Button>
            </div>
          ))}
          <div className="grid gap-2 sm:grid-cols-[1fr_2fr_auto]">
            <Input
              aria-label="New brand social platform"
              value={newSocialPlatform}
              onChange={(event) => setNewSocialPlatform(event.target.value)}
              placeholder="Platform"
              maxLength={50}
            />
            <Input
              aria-label="New brand social profile"
              value={newSocialHandle}
              onChange={(event) => setNewSocialHandle(event.target.value)}
              placeholder="Handle or profile URL"
              maxLength={2048}
            />
            <Button
              type="button"
              variant="outline"
              disabled={
                !newSocialPlatform.trim() ||
                !newSocialHandle.trim() ||
                otherSocials.length + Number(Boolean(instagram.trim())) >= 20
              }
              onClick={() => {
                setOtherSocials((current) => [
                  ...current,
                  {
                    platform: newSocialPlatform.trim(),
                    handle: newSocialHandle.trim(),
                    unverified: true,
                  },
                ]);
                setNewSocialPlatform("");
                setNewSocialHandle("");
              }}
            >
              Add social
            </Button>
          </div>
          <p className="text-xs text-slate-500">
            Social profiles are displayed publicly and are not verified by Collably.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Billing address</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <label className="flex flex-col gap-1 text-sm font-medium sm:col-span-2">
            Address line 1
            <Input
              maxLength={200}
              value={line1}
              onChange={(event) => setLine1(event.target.value)}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium sm:col-span-2">
            Address line 2
            <Input
              maxLength={200}
              value={line2}
              onChange={(event) => setLine2(event.target.value)}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium">
            City
            <Input
              maxLength={120}
              value={city}
              onChange={(event) => setCity(event.target.value)}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium">
            State
            <Input
              maxLength={120}
              value={state}
              onChange={(event) => setState(event.target.value)}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium">
            Postal code
            <Input
              maxLength={20}
              value={postalCode}
              onChange={(event) => setPostalCode(event.target.value)}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium">
            Country code
            <Input
              maxLength={2}
              value={country}
              onChange={(event) => setCountry(event.target.value.toUpperCase())}
              placeholder="IN"
            />
          </label>
        </CardContent>
      </Card>

      {error ? <Alert tone="danger">{error}</Alert> : null}
      {saved ? <Alert tone="success">Profile saved.</Alert> : null}
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={saving || uploadingLogo}>
          {saving ? "Saving…" : "Save changes"}
        </Button>
        <Button
          type="button"
          variant="outline"
          disabled={saving || uploadingLogo}
          onClick={() => {
            setLogoFileId(profile.logo_file_id);
            setCompanyName(profile.company_name ?? "");
            setIndustry(profile.industry ?? "");
            setBrandCity(profile.city ?? "");
            setBrandState(profile.state ?? "");
            setWebsite(profile.website ?? "");
            setContactName(profile.contact_name ?? "");
            setContactEmail(profile.contact_email ?? "");
            setGstin(profile.gstin ?? "");
            setDescription(profile.description ?? "");
            setLine1(profile.billing_address.line1 ?? "");
            setLine2(profile.billing_address.line2 ?? "");
            setCity(profile.billing_address.city ?? "");
            setState(profile.billing_address.state ?? "");
            setPostalCode(profile.billing_address.postal_code ?? "");
            setCountry(profile.billing_address.country ?? "IN");
            setInstagram(
              profile.social_handles?.find(
                (item) => item.platform.toLowerCase() === "instagram",
              )?.handle ?? "",
            );
            setInstagramMetadata(
              profile.social_handles?.find(
                (item) => item.platform.toLowerCase() === "instagram",
              ),
            );
            setOtherSocials(
              (profile.social_handles ?? []).filter(
                (item) => item.platform.toLowerCase() !== "instagram",
              ),
            );
            setNewSocialPlatform("");
            setNewSocialHandle("");
            setError(null);
            setSaved(false);
          }}
        >
          Cancel
        </Button>
        <Link
          href={`/brands/${profile.id}`}
          className="inline-flex items-center rounded-md px-3 py-2 text-sm font-medium text-brand-700 hover:bg-brand-50"
        >
          View public profile
        </Link>
      </div>
    </form>
  );
}

export default function BrandProfilePage() {
  const q = useMyProfile();
  if (q.isLoading) return <LoadingState />;
  if (q.isError) {
    return <ErrorState onRetry={() => q.refetch()} />;
  }
  const profile = q.data?.brand;
  if (!profile) {
    return (
      <EmptyState
        title="No brand profile yet"
        description="Finish onboarding to set up your company details."
      />
    );
  }
  return <BrandProfileEditor key={profile.id} profile={profile} />;
}
