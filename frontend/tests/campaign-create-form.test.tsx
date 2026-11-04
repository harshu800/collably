import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CampaignCreateForm } from "@/components/forms/CampaignCreateForm";

describe("CampaignCreateForm", () => {
  it("requires title, type, and budget", async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();
    render(<CampaignCreateForm onSubmit={onSubmit} />);
    await user.click(screen.getByRole("button", { name: /create campaign/i }));
    expect(onSubmit).not.toHaveBeenCalled();
    expect(
      await screen.findByText(/title must be at least 3 characters/i),
    ).toBeInTheDocument();
    expect(await screen.findByText(/pick a campaign type/i)).toBeInTheDocument();
  });

  it("converts rupees to paise on submit", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<CampaignCreateForm onSubmit={onSubmit} />);
    await user.type(screen.getByLabelText(/title/i), "Festive drop");
    await user.selectOptions(screen.getByLabelText(/campaign type/i), "ugc");
    await user.type(screen.getByLabelText(/budget/i), "500");
    const creators = screen.getByLabelText(/number of creators/i);
    await user.clear(creators);
    await user.type(creators, "2");
    const revisions = screen.getByLabelText(/revision limit/i);
    await user.clear(revisions);
    await user.type(revisions, "1");
    await user.click(screen.getByRole("button", { name: /create campaign/i }));
    expect(onSubmit).toHaveBeenCalledTimes(1);
    const payload = onSubmit.mock.calls[0][0] as Record<string, unknown>;
    expect(payload.budget_paise).toBe(50000);
    expect(payload.type).toBe("ugc");
    expect(payload.number_of_creators).toBe(2);
    expect(payload.revision_limit).toBe(1);
    expect(payload.title).toBe("Festive drop");
  });

  it("rejects a negative revision limit via HTML5 constraint", async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();
    render(<CampaignCreateForm onSubmit={onSubmit} />);
    await user.type(screen.getByLabelText(/title/i), "Launch");
    await user.selectOptions(screen.getByLabelText(/campaign type/i), "ugc");
    await user.type(screen.getByLabelText(/budget/i), "500");
    const revisions = screen.getByLabelText(/revision limit/i);
    await user.clear(revisions);
    await user.type(revisions, "-1");
    await user.click(screen.getByRole("button", { name: /create campaign/i }));
    expect(onSubmit).not.toHaveBeenCalled();
    expect(await screen.findByText(/must be zero or more/i)).toBeInTheDocument();
  });

  it("rejects number_of_creators outside 1..100", async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();
    render(<CampaignCreateForm onSubmit={onSubmit} />);
    await user.type(screen.getByLabelText(/title/i), "Launch");
    await user.selectOptions(screen.getByLabelText(/campaign type/i), "ugc");
    await user.type(screen.getByLabelText(/budget/i), "500");
    const creators = screen.getByLabelText(/number of creators/i);
    await user.clear(creators);
    await user.type(creators, "150");
    await user.click(screen.getByRole("button", { name: /create campaign/i }));
    expect(onSubmit).not.toHaveBeenCalled();
    expect(await screen.findByText(/must be at most 100/i)).toBeInTheDocument();
  });
});
