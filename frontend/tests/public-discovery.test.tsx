import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import LandingPage from "@/app/page";
import CreatorsPage from "@/app/(public)/creators/page";
import PublicCampaignsPage from "@/app/(public)/campaigns/page";

const { useCreatorsMock, useCampaignsMock } = vi.hoisted(() => ({
  useCreatorsMock: vi.fn(),
  useCampaignsMock: vi.fn(),
}));

vi.mock("@/lib/api/queries", () => ({
  useCreators: useCreatorsMock,
  useCampaigns: useCampaignsMock,
}));

describe("public discovery", () => {
  beforeEach(() => {
    useCreatorsMock.mockReset().mockReturnValue({
      data: {
        items: [
          {
            id: "creator-1",
            display_name: "Mira",
            city: "Mumbai",
            state: "Maharashtra",
            does_ugc: true,
            does_influencer: false,
            niches: ["beauty"],
          },
        ],
        total: 21,
      },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    useCampaignsMock.mockReset().mockReturnValue({
      data: {
        items: [
          {
            id: "campaign-1",
            title: "Beauty campaign",
            budget_paise: 50000,
            type: "ugc",
            number_of_creators: 2,
            niches: ["beauty"],
          },
        ],
        total: 21,
      },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
  });

  it("links visitors to creator profiles and brand deals from home", () => {
    render(<LandingPage />);

    expect(screen.getByRole("link", { name: "Browse creators" })).toHaveAttribute(
      "href",
      "/creators",
    );
    expect(screen.getByRole("link", { name: "View brand deals" })).toHaveAttribute(
      "href",
      "/campaigns",
    );
  });

  it("paginates through the public creator directory", () => {
    render(<CreatorsPage />);

    expect(screen.getByText("Page 1 of 2")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));

    expect(useCreatorsMock).toHaveBeenLastCalledWith({
      page: 2,
      page_size: 20,
    });
    expect(screen.getByText("Page 2 of 2")).toBeInTheDocument();
  });

  it("paginates through public brand deals", () => {
    render(<PublicCampaignsPage />);

    expect(screen.getByText("Page 1 of 2")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));

    expect(useCampaignsMock).toHaveBeenLastCalledWith({
      page: 2,
      page_size: 20,
    });
    expect(screen.getByText("Page 2 of 2")).toBeInTheDocument();
  });
});
