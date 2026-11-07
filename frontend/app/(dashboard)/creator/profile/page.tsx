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
import { useApi } from "@/lib/api/useApi";
import { publicFileUrl } from "@/lib/api/client";
import { normalizeSocialHandles } from "@/lib/profile-socials";
import { paiseFromRupees } from "@/lib/money";
import type { CreatorProfileSelf } from "@/lib/api/types";

function splitList(value: string): string[] {
  return [...new Set(value.split(",").map((item) => item.trim()).filter(Boolean))];
}

function CreatorProfileEditor({ profile }: { profile: CreatorProfileSelf }) {
  const api = useApi();
  const updateProfile = useUpdateProfile();
  const [avatarFileId, setAvatarFileId] = React.useState(profile.avatar_file_id);
  const [displayName, setDisplayName] = React.useState(profile.display_name ?? "");
  const [bio, setBio] = React.useState(profile.bio ?? "");
  const [city, setCity] = React.useState(profile.city ?? "");
  const [state, setState] = React.useState(profile.state ?? "");
  const [niches, setNiches] = React.useState(profile.niches.join(", "));
  const [languages, setLanguages] = React.useState(profile.languages.join(", "));
  const [contentTypes, setContentTypes] = React.useState(
    profile.content_types.join(", "),
  );
  const [doesUgc, setDoesUgc] = React.useState(profile.does_ugc);
  const [doesInfluencer, setDoesInfluencer] = React.useState(
    profile.does_influencer,
  );
  const [startingRate, setStartingRate] = React.useState(
    profile.starting_rate_paise == null
      ? ""
      : (profile.starting_rate_paise / 100).toFixed(2),
  );
  const [portfolioLinks, setPortfolioLinks] = React.useState(
    profile.portfolio_links,
  );
  const [newPortfolioLabel, setNewPortfolioLabel] = React.useState("");
  const [newPortfolioUrl, setNewPortfolioUrl] = React.useState("");
  const [instagram, setInstagram] = React.useState(
    profile.social_handles.find(
      (item) => item.platform.toLowerCase() === "instagram",
    )?.handle ?? "",
  );
  const [instagramMetadata, setInstagramMetadata] = React.useState(
    profile.social_handles.find(
      (item) => item.platform.toLowerCase() === "instagram",
    ),
  );
  const [youtubeUrl, setYoutubeUrl] = React.useState(
    profile.social_handles.find(
      (item) => item.platform.toLowerCase() === "youtube",
    )?.handle ?? "",
  );
  const [youtubeMetadata, setYoutubeMetadata] = React.useState(
    profile.social_handles.find(
      (item) => item.platform.toLowerCase() === "youtube",
    ),
  );
  const [otherSocials, setOtherSocials] = React.useState(
    profile.social_handles.filter(
      (item) =>
        !["instagram", "youtube"].includes(item.platform.toLowerCase()),
    ),
  );
  const [newSocialPlatform, setNewSocialPlatform] = React.useState("");
  const [newSocialHandle, setNewSocialHandle] = React.useState("");
  const [uploadingAvatar, setUploadingAvatar] = React.useState(false);
  const [saving, setSaving] = React.useState(false);
  const [uploadingPortfolio, setUploadingPortfolio] = React.useState(false);
  const [portfolioProgress, setPortfolioProgress] = React.useState(0);
  const [error, setError] = React.useState<string | null>(null);
  const [saved, setSaved] = React.useState(false);
  const portfolioInput = React.useRef<HTMLInputElement>(null);

  async function uploadPortfolioFile(file?: File) {
    if (!file) return;
    setError(null);
    if (portfolioLinks.length >= 20) {
      setError("A profile can have up to 20 portfolio links or files.");
      return;
    }
    const maxBytes: Record<string, number> = {
      "image/jpeg": 10 * 1024 * 1024,
      "image/png": 10 * 1024 * 1024,
      "image/webp": 10 * 1024 * 1024,
      "video/mp4": 200 * 1024 * 1024,
      "video/quicktime": 200 * 1024 * 1024,
      "application/pdf": 25 * 1024 * 1024,
    };
    const limit = maxBytes[file.type];
    if (!limit) {
      setError("Choose a JPG, PNG, WebP, MP4, MOV, or PDF file.");
      return;
    }
    if (file.size > limit) {
      setError(`This file exceeds the ${Math.floor(limit / 1024 / 1024)} MB limit.`);
      return;
    }
    const formData = new FormData();
    formData.append("file", file);
    setPortfolioProgress(0);
    setUploadingPortfolio(true);
    try {
      const uploaded = await api.postWithProgress<{ id: string }>(
        "/files/creator-portfolio",
        formData,
        setPortfolioProgress,
      );
      setPortfolioLinks((current) => [
        ...current,
        { label: file.name, url: publicFileUrl(uploaded.id) },
      ]);
      setPortfolioProgress(100);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Could not upload the portfolio file.",
      );
    } finally {
      setUploadingPortfolio(false);
      if (portfolioInput.current) portfolioInput.current.value = "";
    }
  }

  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSaved(false);
    if (!doesUgc && !doesInfluencer) {
      setError("Choose UGC creator, influencer, or both.");
      return;
    }
    setSaving(true);

    try {
      const normalizedInstagram = instagram.trim().replace(/^@+/, "");
      const normalizedYouTube = youtubeUrl.trim();
      await updateProfile.mutateAsync({
        avatar_file_id: avatarFileId,
        display_name: displayName.trim() || null,
        bio: bio.trim() || null,
        city: city.trim() || null,
        state: state.trim() || null,
        niches: splitList(niches),
        languages: splitList(languages),
        content_types: splitList(contentTypes),
        does_ugc: doesUgc,
        does_influencer: doesInfluencer,
        starting_rate_paise:
          startingRate.trim() === "" ? null : paiseFromRupees(startingRate),
        portfolio_links: portfolioLinks,
        social_handles: normalizeSocialHandles([
          ...otherSocials,
          ...(normalizedInstagram
            ? [
                {
                  platform: "Instagram",
                  handle: `@${normalizedInstagram}`,
                  follower_count: instagramMetadata?.follower_count,
                  unverified: instagramMetadata?.unverified ?? true,
                },
              ]
            : []),
          ...(normalizedYouTube
            ? [
                {
                  platform: "YouTube",
                  handle: normalizedYouTube,
                  follower_count: youtubeMetadata?.follower_count,
                  unverified: youtubeMetadata?.unverified ?? true,
                },
              ]
            : []),
        ]),
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
        <h1 className="text-2xl font-bold">Your creator profile</h1>
        <p className="mt-1 text-sm text-slate-600">
          Add a profile photo, Instagram handle, and portfolio so brands can
          learn about your work. Creator profile details are public. Save
          changes to publish your edits and uploads.
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Profile picture</CardTitle>
        </CardHeader>
        <CardContent>
          <ProfileImageUpload
            fileId={avatarFileId}
            onChange={setAvatarFileId}
            onUploadingChange={setUploadingAvatar}
            label="profile picture"
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>About you</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <label className="flex flex-col gap-1 text-sm font-medium">
            Full name
            <Input
              maxLength={120}
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              placeholder="Your name"
              aria-label="Full name"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium">
            Starting rate (INR)
            <Input
              type="number"
              min="0"
              step="0.01"
              value={startingRate}
              onChange={(event) => setStartingRate(event.target.value)}
              placeholder="e.g. 2500"
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
          <label className="flex flex-col gap-1 text-sm font-medium sm:col-span-2">
            Bio
            <Textarea
              maxLength={2000}
              rows={4}
              value={bio}
              onChange={(event) => setBio(event.target.value)}
              placeholder="Tell brands about yourself and your work"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium sm:col-span-2">
            Niches (comma separated)
            <Input
              value={niches}
              onChange={(event) => setNiches(event.target.value)}
              placeholder="beauty, lifestyle"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium sm:col-span-2">
            Languages (comma separated)
            <Input
              value={languages}
              onChange={(event) => setLanguages(event.target.value)}
              placeholder="Hindi, English"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium sm:col-span-2">
            Content types (comma separated)
            <Input
              value={contentTypes}
              onChange={(event) => setContentTypes(event.target.value)}
              placeholder="Short-form video, product photography"
            />
          </label>
          <fieldset className="flex flex-wrap gap-5 text-sm sm:col-span-2">
            <legend className="mb-2 w-full font-medium">Creator type</legend>
            <label className="flex items-center gap-2">
              <input
                type="radio"
                name="creator-type"
                checked={doesUgc}
                onChange={() => {
                  setDoesUgc(true);
                  setDoesInfluencer(false);
                }}
              />
              UGC creator
            </label>
            <label className="flex items-center gap-2">
              <input
                type="radio"
                name="creator-type"
                checked={!doesUgc && doesInfluencer}
                onChange={() => {
                  setDoesUgc(false);
                  setDoesInfluencer(true);
                }}
              />
              Influencer
            </label>
            <label className="flex items-center gap-2">
              <input
                type="radio"
                name="creator-type"
                checked={doesUgc && doesInfluencer}
                onChange={() => {
                  setDoesUgc(true);
                  setDoesInfluencer(true);
                }}
              />
              Both
            </label>
          </fieldset>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Social profile</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <label className="flex max-w-xl flex-col gap-1 text-sm font-medium">
            Instagram handle
            <Input
              value={instagram}
              onChange={(event) => setInstagram(event.target.value)}
              placeholder="@yourhandle"
              maxLength={120}
              aria-label="Instagram handle"
            />
            <span className="font-normal text-slate-500">
              The handle is displayed publicly and is not verified by Collably.
            </span>
          </label>
          <label className="flex max-w-xl flex-col gap-1 text-sm font-medium">
            YouTube URL
            <Input
              type="url"
              value={youtubeUrl}
              onChange={(event) => setYoutubeUrl(event.target.value)}
              placeholder="https://youtube.com/@yourchannel"
              maxLength={2048}
            />
          </label>
          {otherSocials.map((social, index) => (
            <div
              key={`${social.platform}-${index}`}
              className="grid gap-2 sm:grid-cols-[1fr_2fr_auto]"
            >
              <Input
                aria-label={`Social platform ${index + 1}`}
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
                aria-label={`Social handle or URL ${index + 1}`}
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
              aria-label="New social platform"
              value={newSocialPlatform}
              onChange={(event) => setNewSocialPlatform(event.target.value)}
              placeholder="Platform"
              maxLength={50}
            />
            <Input
              aria-label="New social handle or URL"
              value={newSocialHandle}
              onChange={(event) => setNewSocialHandle(event.target.value)}
              placeholder="Handle or profile URL"
              maxLength={2048}
            />
            <Button
              type="button"
              variant="outline"
              disabled={              !newSocialPlatform.trim() ||
              !newSocialHandle.trim() ||
              otherSocials.length +
                Number(Boolean(instagram.trim())) +
                Number(Boolean(youtubeUrl.trim())) >=
                20}
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
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Portfolio</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {portfolioLinks.length ? (
            <ul className="flex flex-col gap-2">
              {portfolioLinks.map((link, index) => (
                <li
                  key={`${link.url}-${index}`}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-slate-200 p-3 text-sm"
                >
                  <a
                    className="break-all text-brand-600 underline"
                    href={link.url}
                    target="_blank"
                    rel="noreferrer noopener"
                  >
                    {link.label}
                  </a>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() =>
                      setPortfolioLinks((current) =>
                        current.filter((_, currentIndex) => currentIndex !== index),
                      )
                    }
                  >
                    Remove
                  </Button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-slate-500">No portfolio items added yet.</p>
          )}
          <div className="grid gap-2 sm:grid-cols-[1fr_2fr_auto]">
            <Input
              value={newPortfolioLabel}
              onChange={(event) => setNewPortfolioLabel(event.target.value)}
              placeholder="Link label"
              aria-label="Portfolio link label"
            />
            <Input
              type="url"
              value={newPortfolioUrl}
              onChange={(event) => setNewPortfolioUrl(event.target.value)}
              placeholder="https://"
              aria-label="Portfolio link URL"
            />
            <Button
              type="button"
              variant="outline"
              disabled={
                !newPortfolioLabel.trim() ||
                !newPortfolioUrl.trim() ||
                portfolioLinks.length >= 20
              }
              onClick={() => {
                setPortfolioLinks((current) => [
                  ...current,
                  {
                    label: newPortfolioLabel.trim(),
                    url: newPortfolioUrl.trim(),
                  },
                ]);
                setNewPortfolioLabel("");
                setNewPortfolioUrl("");
              }}
            >
              Add link
            </Button>
          </div>
          <div>
            <input
              ref={portfolioInput}
              className="sr-only"
              type="file"
              accept="image/jpeg,image/png,image/webp,video/mp4,video/quicktime,application/pdf"
              aria-label="Choose portfolio file"
              onChange={(event) =>
                void uploadPortfolioFile(event.currentTarget.files?.[0])
              }
            />
            <Button
              type="button"
              variant="outline"
              disabled={uploadingPortfolio}
              onClick={() => portfolioInput.current?.click()}
            >
              {uploadingPortfolio ? "Uploading…" : "Upload portfolio file"}
            </Button>
            <p className="mt-1 text-xs text-slate-500">
              Images (10 MB max), videos (200 MB max), or PDF (25 MB max).
              Uploaded portfolio files are public. Save changes to add them to
              your profile.
            </p>
            {uploadingPortfolio ? (
              <div className="mt-2 max-w-xs">
                <progress
                  className="w-full"
                  value={portfolioProgress}
                  max={100}
                  aria-label="Portfolio upload progress"
                />
                <span className="text-xs text-slate-600">
                  {portfolioProgress}% uploaded
                </span>
              </div>
            ) : null}
          </div>
        </CardContent>
      </Card>

      {error ? <Alert tone="danger">{error}</Alert> : null}
      {saved ? <Alert tone="success">Profile saved.</Alert> : null}
      <div className="flex gap-2">
        <Button
          type="submit"
          disabled={saving || uploadingPortfolio || uploadingAvatar}
        >
          {saving ? "Saving…" : "Save changes"}
        </Button>
        <Button
          type="button"
          variant="outline"
          disabled={saving || uploadingPortfolio || uploadingAvatar}
          onClick={() => {
            setAvatarFileId(profile.avatar_file_id);
            setDisplayName(profile.display_name ?? "");
            setBio(profile.bio ?? "");
            setCity(profile.city ?? "");
            setState(profile.state ?? "");
            setNiches(profile.niches.join(", "));
            setLanguages(profile.languages.join(", "));
            setContentTypes(profile.content_types.join(", "));
            setDoesUgc(profile.does_ugc);
            setDoesInfluencer(profile.does_influencer);
            setStartingRate(
              profile.starting_rate_paise == null
                ? ""
                : (profile.starting_rate_paise / 100).toFixed(2),
            );
            setPortfolioLinks(profile.portfolio_links);
            setNewPortfolioLabel("");
            setNewPortfolioUrl("");
            setInstagram(
              profile.social_handles.find(
                (item) => item.platform.toLowerCase() === "instagram",
              )?.handle ?? "",
            );
            setInstagramMetadata(
              profile.social_handles.find(
                (item) => item.platform.toLowerCase() === "instagram",
              ),
            );
            setYoutubeUrl(
              profile.social_handles.find(
                (item) => item.platform.toLowerCase() === "youtube",
              )?.handle ?? "",
            );
            setYoutubeMetadata(
              profile.social_handles.find(
                (item) => item.platform.toLowerCase() === "youtube",
              ),
            );
            setOtherSocials(
              profile.social_handles.filter(
                (item) =>
                  !["instagram", "youtube"].includes(
                    item.platform.toLowerCase(),
                  ),
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
        {profile.is_onboarded ? (
          <Link
            href={`/creators/${profile.id}`}
            className="inline-flex items-center rounded-md px-3 py-2 text-sm font-medium text-brand-700 hover:bg-brand-50"
          >
            View public profile
          </Link>
        ) : (
          <p className="self-center text-sm text-slate-500">
            Complete your required details and save to publish your profile.
          </p>
        )}
      </div>
    </form>
  );
}

export default function CreatorProfilePage() {
  const q = useMyProfile();
  if (q.isLoading) return <LoadingState />;
  if (q.isError) {
    return (
      <ErrorState
        description="Could not load your profile."
        onRetry={() => q.refetch()}
      />
    );
  }
  const profile = q.data?.creator;
  if (!profile) {
    return (
      <EmptyState
        title="No profile yet"
        description="Finish onboarding to set up your creator profile."
      />
    );
  }
  return <CreatorProfileEditor key={profile.id} profile={profile} />;
}
