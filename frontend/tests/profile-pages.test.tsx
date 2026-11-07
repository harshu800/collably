import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import CreatorProfilePage from "@/app/(dashboard)/creator/profile/page";
import BrandProfilePage from "@/app/(dashboard)/brand/profile/page";
import BrandPublicProfilePage from "@/app/(public)/brands/[id]/page";

const {
  useMyProfileMock,
  usePublicBrandMock,
  useUpdateProfileMock,
  useApiMock,
} = vi.hoisted(() => ({
  useMyProfileMock: vi.fn(),
  usePublicBrandMock: vi.fn(),
  useUpdateProfileMock: vi.fn(),
  useApiMock: vi.fn(),
}));

vi.mock("@/lib/api/queries", () => ({
  useMyProfile: useMyProfileMock,
  usePublicBrand: usePublicBrandMock,
  useUpdateProfile: useUpdateProfileMock,
}));

vi.mock("@/lib/api/useApi", () => ({
  useApi: useApiMock,
}));

describe("profile pages", () => {
  beforeEach(() => {
    useMyProfileMock.mockReset();
    usePublicBrandMock.mockReset();
    useUpdateProfileMock.mockReturnValue({ mutateAsync: vi.fn() });
    useApiMock.mockReturnValue({ post: vi.fn() });
  });

  it("shows editable creator details instead of raw JSON", () => {
    useMyProfileMock.mockReturnValue({
      data: {
        role: "creator",
        creator: {
          display_name: "Mira Sharma",
          city: "Mumbai",
          state: "Maharashtra",
          bio: "Beauty creator",
          languages: ["Hindi", "English"],
          niches: ["beauty"],
          does_ugc: true,
          does_influencer: false,
          content_types: ["Short-form video"],
          starting_rate_paise: 250000,
          portfolio_links: [
            { label: "My work", url: "https://example.com/portfolio" },
          ],
          social_handles: [
            {
              platform: "YouTube",
              handle: "https://youtube.com/@mira",
              unverified: true,
            },
          ],
        },
      },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });

    const { container } = render(<CreatorProfilePage />);

    expect(
      screen.getByRole("heading", { name: "Your creator profile" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Full name")).toHaveValue("Mira Sharma");
    expect(screen.getByLabelText("City")).toHaveValue("Mumbai");
    expect(screen.getByLabelText("State")).toHaveValue("Maharashtra");
    expect(screen.getByLabelText("Instagram handle")).toHaveValue("");
    expect(screen.getByLabelText("YouTube URL")).toHaveValue(
      "https://youtube.com/@mira",
    );
    expect(
      screen.getByRole("button", { name: "Upload portfolio file" }),
    ).toBeInTheDocument();
    expect(container.querySelector("pre")).toBeNull();
  });

  it("normalizes creator social handles without losing verification status", async () => {
    const mutateAsync = vi.fn().mockResolvedValue({});
    useUpdateProfileMock.mockReturnValue({ mutateAsync });
    useMyProfileMock.mockReturnValue({
      data: {
        role: "creator",
        creator: {
          id: "creator-1",
          display_name: "Mira Sharma",
          avatar_file_id: null,
          bio: "Beauty creator",
          city: "Mumbai",
          state: "Maharashtra",
          languages: ["English"],
          niches: ["beauty"],
          does_ugc: true,
          does_influencer: false,
          content_types: ["Video"],
          starting_rate_paise: null,
          currency: "INR",
          portfolio_links: [],
          social_handles: [
            {
              platform: "TikTok",
              handle: "@mira",
              follower_count: 77,
              unverified: false,
              legacy_note: "must not be sent",
            },
            {
              platform: "Instagram",
              handle: "@mira",
              follower_count: 88,
              unverified: false,
              legacy_id: "old",
            },
            {
              platform: "YouTube",
              handle: "https://youtube.com/@mira",
              unverified: true,
              legacy_id: "old",
            },
          ],
          is_onboarded: true,
        },
      },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });

    const { container } = render(<CreatorProfilePage />);
    fireEvent.submit(container.querySelector("form")!);

    await waitFor(() => expect(mutateAsync).toHaveBeenCalledOnce());
    expect(mutateAsync.mock.calls[0][0].social_handles).toEqual([
      {
        platform: "TikTok",
        handle: "@mira",
        follower_count: 77,
        unverified: false,
      },
      {
        platform: "Instagram",
        handle: "@mira",
        follower_count: 88,
        unverified: false,
      },
      {
        platform: "YouTube",
        handle: "https://youtube.com/@mira",
        unverified: true,
      },
    ]);
  });

  it("shows editable brand details instead of raw JSON", () => {
    useMyProfileMock.mockReturnValue({
      data: {
        role: "brand",
        brand: {
          company_name: "Good Goods",
          city: "Mumbai",
          state: "Maharashtra",
          social_handles: [
            {
              platform: "Instagram",
              handle: "@goodgoods",
              unverified: true,
            },
          ],
          industry: "Beauty",
          contact_name: "Asha Rao",
          contact_email: "asha@example.com",
          website: "https://example.com",
          gstin: null,
          billing_address: {
            line1: "12 Market Road",
            city: "Mumbai",
            state: "Maharashtra",
            postal_code: "400001",
            country: "IN",
          },
          description: "Independent skincare brand",
        },
      },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });

    const { container } = render(<BrandProfilePage />);

    expect(screen.getByLabelText("Company name")).toHaveValue("Good Goods");
    expect(screen.getByLabelText("Contact name")).toHaveValue("Asha Rao");
    expect(screen.getByLabelText("Contact email")).toHaveValue("asha@example.com");
    expect(screen.getByLabelText("Address line 1")).toHaveValue("12 Market Road");
    expect(screen.getByLabelText("Company city")).toHaveValue("Mumbai");
    expect(screen.getByLabelText("Instagram handle")).toHaveValue("@goodgoods");
    expect(container.querySelector("pre")).toBeNull();
  });

  it("normalizes brand social handles without losing verification status", async () => {
    const mutateAsync = vi.fn().mockResolvedValue({});
    useUpdateProfileMock.mockReturnValue({ mutateAsync });
    useMyProfileMock.mockReturnValue({
      data: {
        role: "brand",
        brand: {
          id: "brand-1",
          company_name: "Good Goods",
          website: "https://example.com",
          logo_file_id: null,
          industry: "Beauty",
          city: "Mumbai",
          state: "Maharashtra",
          contact_name: "Asha Rao",
          contact_email: "asha@example.com",
          gstin: null,
          billing_address: {},
          description: "Independent skincare brand",
          social_handles: [
            {
              platform: "LinkedIn",
              handle: "https://linkedin.com/company/goodgoods",
              unverified: true,
              legacy_note: "must not be sent",
            },
            {
              platform: "Instagram",
              handle: "@goodgoods",
              follower_count: 123,
              unverified: false,
              legacy_id: "old",
            },
          ],
          is_onboarded: true,
        },
      },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });

    const { container } = render(<BrandProfilePage />);
    fireEvent.submit(container.querySelector("form")!);

    await waitFor(() => expect(mutateAsync).toHaveBeenCalledOnce());
    expect(mutateAsync.mock.calls[0][0].social_handles).toEqual([
      {
        platform: "LinkedIn",
        handle: "https://linkedin.com/company/goodgoods",
        unverified: true,
      },
      {
        platform: "Instagram",
        handle: "@goodgoods",
        follower_count: 123,
        unverified: false,
      },
    ]);
  });

  it("renders a public brand profile without requiring private contact data", () => {
    usePublicBrandMock.mockReturnValue({
      data: {
        id: "brand-1",
        company_name: "Good Goods",
        website: "https://example.com",
        logo_file_id: null,
        industry: "Beauty",
        city: "Mumbai",
        state: "Maharashtra",
        description: "Independent skincare brand",
        social_handles: [
          {
            platform: "Instagram",
            handle: "@goodgoods",
            unverified: true,
          },
        ],
      },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });

    render(<BrandPublicProfilePage params={{ id: "brand-1" }} />);

    expect(
      screen.getByRole("heading", { name: "Good Goods" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Independent skincare brand")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "@goodgoods" })).toHaveAttribute(
      "href",
      "https://www.instagram.com/goodgoods",
    );
  });
});
