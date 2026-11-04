import { z } from "zod";
import { paiseFromRupees } from "@/lib/money";

export const campaignCreateSchema = z.object({
  title: z
    .string({ required_error: "Title is required" })
    .trim()
    .min(3, "Title must be at least 3 characters")
    .max(200, "Title is too long"),
  description: z.string().trim().max(5000).optional().or(z.literal("")),
  type: z
    .enum(["ugc", "influencer", "hybrid"], {
      errorMap: () => ({ message: "Pick a campaign type" }),
    }),
  budget_rupees: z
    .string({ required_error: "Budget is required" })
    .trim()
    .refine((v) => /^\d+(\.\d{1,2})?$/.test(v), {
      message: "Enter a budget in rupees, up to two decimal places",
    }),
  number_of_creators: z.coerce
    .number()
    .int("Must be a whole number")
    .min(1, "Must be at least 1")
    .max(100, "Must be at most 100"),
  revision_limit: z.coerce
    .number()
    .int("Must be a whole number")
    .min(0, "Must be zero or more")
    .max(10, "Must be at most 10"),
  usage_rights: z.string().trim().max(5000).optional().or(z.literal("")),
  disclosure_required: z.boolean().optional(),
});
export type CampaignCreateInput = z.infer<typeof campaignCreateSchema>;

/** Convert validated form input into the API payload shape (paise, trimmed). */
export function campaignCreateToApi(
  input: CampaignCreateInput,
): Record<string, unknown> {
  return {
    title: input.title,
    description: input.description ? input.description : undefined,
    type: input.type,
    budget_paise: paiseFromRupees(input.budget_rupees),
    number_of_creators: input.number_of_creators,
    revision_limit: input.revision_limit,
    usage_rights: input.usage_rights ? input.usage_rights : undefined,
    disclosure_required: input.disclosure_required ?? true,
    deliverable_spec: [],
  };
}
