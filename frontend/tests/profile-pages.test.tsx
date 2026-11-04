import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import CreatorProfilePage from "@/app/(dashboard)/creator/profile/page";
import BrandProfilePage from "@/app/(dashboard)/brand/profile/page";

const { useMyProfileMock } = vi.hoisted(() => ({
  useMyProfileMock: vi.fn(),
}));

vi.mock("@/lib/api/queries", () => ({
  useMyProfile: useMyProfileMock,
}));

describe("profile pages", () => {
  beforeEach(() => {
    useMyProfileMock.mockReset();
  });

  it("shows creator profile details instead of raw JSON", () => {
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
          social_handles: [],
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
    expect(screen.getByText("Mira Sharma")).toBeInTheDocument();
    expect(screen.getByText("Mumbai, Maharashtra")).toBeInTheDocument();
    expect(screen.getByText("₹2,500.00")).toBeInTheDocument();
    expect(container.querySelector("pre")).toBeNull();
  });

  it("shows brand profile details instead of raw JSON", () => {
    useMyProfileMock.mockReturnValue({
      data: {
        role: "brand",
        brand: {
          company_name: "Good Goods",
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

    expect(screen.getByText("Good Goods")).toBeInTheDocument();
    expect(screen.getByText("Asha Rao")).toBeInTheDocument();
    expect(screen.getByText("asha@example.com")).toBeInTheDocument();
    expect(
      screen.getByText("12 Market Road, Mumbai, Maharashtra, 400001, IN"),
    ).toBeInTheDocument();
    expect(container.querySelector("pre")).toBeNull();
  });
});
