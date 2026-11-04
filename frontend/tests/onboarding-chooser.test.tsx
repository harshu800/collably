import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const replace = vi.fn();

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({ isLoaded: true, isSignedIn: true, userId: "user_x" }),
  useUser: () => ({
    user: {
      id: "user_x",
      primaryEmailAddress: { emailAddress: "pat@example.com" },
    },
  }),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push: vi.fn() }),
}));

const get = vi.fn().mockResolvedValue({
  id: "u1",
  role: null,
  email: "pat@example.com",
});
const post = vi.fn().mockResolvedValue({
  id: "u1",
  role: "creator",
  email: "pat@example.com",
});

vi.mock("@/lib/api/useApi", () => ({
  useApi: () => ({ get, post }),
}));

import OnboardingPage from "@/app/onboarding/page";

describe("OnboardingPage chooser", () => {
  it("POSTs the selected role and routes to the role home", async () => {
    const user = userEvent.setup();
    render(<OnboardingPage />);
    const button = await screen.findByRole("button", {
      name: /continue as a creator/i,
    });
    await user.click(button);
    await waitFor(() => {
      expect(post).toHaveBeenCalledWith("/users/me/role", {
        body: { role: "creator" },
      });
    });
    await waitFor(() => {
      expect(replace).toHaveBeenCalledWith("/creator/overview");
    });
  });
});
