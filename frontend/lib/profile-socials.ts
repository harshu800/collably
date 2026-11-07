export interface ProfileSocialHandle {
  platform: string;
  handle: string;
  follower_count?: number | null;
  unverified: boolean;
}

export function normalizeSocialHandles(
  entries: readonly unknown[],
): ProfileSocialHandle[] {
  const normalized: ProfileSocialHandle[] = [];

  for (const entry of entries) {
    if (!entry || typeof entry !== "object") continue;

    const record = entry as Record<string, unknown>;
    if (
      typeof record.platform !== "string" ||
      typeof record.handle !== "string"
    ) {
      continue;
    }

    const platform = record.platform.trim();
    const handle = record.handle.trim();
    if (!platform || !handle) continue;

    const social: ProfileSocialHandle = {
      platform,
      handle,
      unverified:
        typeof record.unverified === "boolean" ? record.unverified : true,
    };
    const followerCount = record.follower_count;
    if (
      followerCount === null ||
      (typeof followerCount === "number" &&
        Number.isSafeInteger(followerCount) &&
        followerCount >= 0 &&
        followerCount <= 10_000_000_000)
    ) {
      social.follower_count = followerCount;
    }
    normalized.push(social);
  }

  return normalized;
}
