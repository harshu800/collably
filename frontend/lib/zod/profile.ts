import { z } from "zod";

export const creatorOnboardingSchema = z.object({
  display_name: z.string().trim().min(1).max(120),
  bio: z.string().trim().max(2000).optional().or(z.literal("")),
  city: z.string().trim().max(120).optional().or(z.literal("")),
  state: z.string().trim().max(120).optional().or(z.literal("")),
  languages: z.string().trim().max(500).optional().or(z.literal("")),
  niches: z.string().trim().max(500).optional().or(z.literal("")),
  does_ugc: z.boolean().optional(),
  does_influencer: z.boolean().optional(),
  content_types: z.string().trim().max(500).optional().or(z.literal("")),
  starting_rate_rupees: z
    .string()
    .trim()
    .refine(
      (v) => v === "" || /^\d+(\.\d{1,2})?$/.test(v),
      "Enter a rupee amount, up to two decimal places",
    )
    .optional()
    .or(z.literal("")),
});
export type CreatorOnboardingInput = z.infer<typeof creatorOnboardingSchema>;

export const brandOnboardingSchema = z.object({
  company_name: z.string().trim().min(1).max(200),
  website: z.string().trim().url().optional().or(z.literal("")),
  industry: z.string().trim().max(120).optional().or(z.literal("")),
  contact_name: z.string().trim().max(200).optional().or(z.literal("")),
  contact_email: z.string().trim().email().optional().or(z.literal("")),
  gstin: z
    .string()
    .trim()
    .transform((v) => v.toUpperCase())
    .refine(
      (v) =>
        v === "" ||
        /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$/.test(v),
      "GSTIN must be 15 characters in the Indian GSTIN format",
    )
    .optional()
    .or(z.literal("")),
});
export type BrandOnboardingInput = z.infer<typeof brandOnboardingSchema>;
