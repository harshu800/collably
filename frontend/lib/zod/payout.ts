import { z } from "zod";

const UPI_VPA = /^[a-zA-Z0-9._-]{2,100}@[a-zA-Z][a-zA-Z0-9.-]{1,100}$/;
const IFSC = /^[A-Z]{4}0[A-Z0-9]{6}$/;
const ACCOUNT_NUMBER = /^[0-9]{6,20}$/;

const upiSchema = z.object({
  method: z.literal("upi"),
  label: z.string().trim().max(100).optional().or(z.literal("")),
  holder_name: z.string().trim().min(2).max(100),
  upi_vpa: z
    .string()
    .trim()
    .regex(UPI_VPA, "Enter a valid UPI VPA, e.g. name@okbank"),
});
const bankSchema = z.object({
  method: z.literal("bank"),
  label: z.string().trim().max(100).optional().or(z.literal("")),
  holder_name: z.string().trim().min(2).max(100),
  account_number: z
    .string()
    .trim()
    .regex(ACCOUNT_NUMBER, "6–20 digit account number"),
  ifsc: z
    .string()
    .trim()
    .transform((v) => v.toUpperCase())
    .refine((v) => IFSC.test(v), "Enter a valid 11-char IFSC"),
});
export const payoutMethodSchema = z.discriminatedUnion("method", [
  upiSchema,
  bankSchema,
]);
export type PayoutMethodInput = z.infer<typeof payoutMethodSchema>;
