import { z } from "zod";

export const deliverableSubmitSchema = z
  .object({
    spec_index: z.coerce.number().int().min(0),
    kind: z.enum(["file", "link"]),
    file_id: z.string().uuid().optional(),
    external_url: z.string().trim().url().optional(),
    caption: z.string().trim().max(2000).optional().or(z.literal("")),
  })
  .refine(
    (v) => (v.kind === "file" ? !!v.file_id : !!v.external_url),
    "Provide a file (upload) for file deliverables or a URL for link deliverables.",
  );
export type DeliverableSubmitInput = z.infer<typeof deliverableSubmitSchema>;

export const revisionRequestSchema = z.object({
  note: z
    .string({ required_error: "Add a short note so the creator knows what to change." })
    .trim()
    .min(1, "Add a short note so the creator knows what to change.")
    .max(2000),
});
export type RevisionRequestInput = z.infer<typeof revisionRequestSchema>;
