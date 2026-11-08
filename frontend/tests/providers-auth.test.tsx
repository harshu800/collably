import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { useQuery } from "@tanstack/react-query";
import { AppProviders } from "@/lib/providers";

const authState = vi.hoisted(() => ({ userId: "user-a" }));

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({ userId: authState.userId }),
}));

function AccountDataProbe() {
  const query = useQuery({
    queryKey: ["account"],
    queryFn: async () => authState.userId,
  });
  return <span>{query.data ?? "Loading"}</span>;
}

describe("AppProviders authentication cache", () => {
  afterEach(() => {
    cleanup();
  });

  it("does not reuse cached account data after switching users", async () => {
    const view = render(
      <AppProviders>
        <AccountDataProbe />
      </AppProviders>,
    );
    expect(await screen.findByText("user-a")).toBeInTheDocument();

    authState.userId = "user-b";
    view.rerender(
      <AppProviders>
        <AccountDataProbe />
      </AppProviders>,
    );

    expect(await screen.findByText("user-b")).toBeInTheDocument();
  });
});
