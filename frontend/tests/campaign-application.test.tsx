import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import CampaignDetailPage from "@/app/(public)/campaigns/[id]/page";

const {
  useAuthMock,
  useCampaignMock,
  useMyProfileMock,
  useSubmitApplicationMock,
  mutateAsyncMock,
} = vi.hoisted(() => ({
  useAuthMock: vi.fn(),
  useCampaignMock: vi.fn(),
  useMyProfileMock: vi.fn(),
  useSubmitApplicationMock: vi.fn(),
  mutateAsyncMock: vi.fn(),
}));

vi.mock("@clerk/nextjs", () => ({
  useAuth: useAuthMock,
}));

vi.mock("@/lib/api/queries", () => ({
  useCampaign: useCampaignMock,
  useMyProfile: useMyProfileMock,
  useSubmitApplication: useSubmitApplicationMock,
}));

describe("public campaign applications", () => {
  beforeEach(() => {
    useAuthMock.mockReturnValue({ isLoaded: true, isSignedIn: true });
    useCampaignMock.mockReturnValue({
      data: {
        id: "campaign-1",
        title: "Beauty campaign",
        type: "ugc",
        status: "open",
        niches: ["beauty"],
        description: null,
        budget_paise: 50000,
        revision_limit: 1,
        number_of_creators: 2,
        submission_deadline: null,
        usage_rights: null,
      },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    useMyProfileMock.mockReturnValue({
      data: { role: "creator" },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    mutateAsyncMock.mockReset().mockResolvedValue({});
    useSubmitApplicationMock.mockReturnValue({
      mutateAsync: mutateAsyncMock,
      isPending: false,
    });
  });

  it("lets a signed-in creator apply and links to their applications", async () => {
    const user = userEvent.setup();
    render(<CampaignDetailPage params={{ id: "campaign-1" }} />);

    await user.click(
      screen.getByRole("button", { name: "Apply for collaboration" }),
    );

    expect(mutateAsyncMock).toHaveBeenCalledWith({
      pitch: "I would like to apply.",
    });
    expect(await screen.findByText("Your application has been sent.")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "View your applications" }),
    ).toHaveAttribute("href", "/creator/applications");
  });

  it("asks anonymous visitors to sign in before applying", () => {
    useAuthMock.mockReturnValue({ isLoaded: true, isSignedIn: false });
    render(<CampaignDetailPage params={{ id: "campaign-1" }} />);

    expect(
      screen.getByRole("link", { name: "Sign in to apply for collaboration" }),
    ).toHaveAttribute(
      "href",
      "/sign-in?next=%2Fcampaigns%2Fcampaign-1",
    );
    expect(mutateAsyncMock).not.toHaveBeenCalled();
  });

  it("shows submission errors instead of hiding them", async () => {
    mutateAsyncMock.mockRejectedValueOnce(new Error("Already applied"));
    render(<CampaignDetailPage params={{ id: "campaign-1" }} />);

    fireEvent.click(
      screen.getByRole("button", { name: "Apply for collaboration" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent("Already applied");
  });
});
