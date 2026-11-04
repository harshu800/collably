"use client";

import * as React from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  campaignCreateSchema,
  campaignCreateToApi,
  type CampaignCreateInput,
} from "@/lib/zod/campaign";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { FormField, FormHint, FormMessage } from "@/components/ui/form";
import { Alert } from "@/components/ui/alert";

export interface CampaignCreateFormProps {
  onSubmit: (payload: Record<string, unknown>) => Promise<void>;
}

export function CampaignCreateForm({ onSubmit }: CampaignCreateFormProps) {
  const [serverError, setServerError] = React.useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<CampaignCreateInput>({
    resolver: zodResolver(campaignCreateSchema),
    mode: "onSubmit",
    defaultValues: {
      title: "",
      description: "",
      type: undefined as unknown as "ugc",
      budget_rupees: "",
      number_of_creators: 1,
      revision_limit: 1,
      usage_rights: "",
      disclosure_required: true,
    },
  });

  const submit = handleSubmit(async (values) => {
    setServerError(null);
    try {
      await onSubmit(campaignCreateToApi(values));
    } catch (e) {
      setServerError(
        e instanceof Error ? e.message : "Could not create the campaign.",
      );
    }
  });

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-4">
      <FormField>
        <Label htmlFor="campaign-title">Title</Label>
        <Input
          id="campaign-title"
          {...register("title")}
          aria-invalid={errors.title ? "true" : undefined}
        />
        <FormMessage>{errors.title?.message}</FormMessage>
      </FormField>
      <FormField>
        <Label htmlFor="campaign-type">Campaign type</Label>
        <Select
          id="campaign-type"
          defaultValue=""
          {...register("type")}
          aria-invalid={errors.type ? "true" : undefined}
        >
          <option value="" disabled>
            Pick one
          </option>
          <option value="ugc">UGC — creator makes content for you</option>
          <option value="influencer">
            Influencer — creator posts to their audience
          </option>
          <option value="hybrid">Hybrid — both</option>
        </Select>
        <FormMessage>{errors.type?.message}</FormMessage>
      </FormField>
      <FormField>
        <Label htmlFor="campaign-budget">Budget (₹)</Label>
        <Input
          id="campaign-budget"
          inputMode="decimal"
          placeholder="500"
          {...register("budget_rupees")}
          aria-invalid={errors.budget_rupees ? "true" : undefined}
        />
        <FormHint>
          Enter in rupees. We convert to paise on submit — e.g. 500 ₹ saves as 50000.
        </FormHint>
        <FormMessage>{errors.budget_rupees?.message}</FormMessage>
      </FormField>
      <FormField>
        <Label htmlFor="campaign-creators">Number of creators</Label>
        <Input
          id="campaign-creators"
          type="number"
          min={1}
          max={100}
          {...register("number_of_creators")}
          aria-invalid={errors.number_of_creators ? "true" : undefined}
        />
        <FormMessage>{errors.number_of_creators?.message}</FormMessage>
      </FormField>
      <FormField>
        <Label htmlFor="campaign-revisions">Revision limit</Label>
        <Input
          id="campaign-revisions"
          type="number"
          min={0}
          max={10}
          {...register("revision_limit")}
          aria-invalid={errors.revision_limit ? "true" : undefined}
        />
        <FormMessage>{errors.revision_limit?.message}</FormMessage>
      </FormField>
      <FormField>
        <Label htmlFor="campaign-description">Description</Label>
        <Textarea
          id="campaign-description"
          rows={4}
          {...register("description")}
        />
      </FormField>
      <FormField>
        <Label htmlFor="campaign-usage">Usage rights</Label>
        <Textarea
          id="campaign-usage"
          rows={3}
          {...register("usage_rights")}
        />
      </FormField>
      <label className="flex items-center gap-2 text-sm">
        <Checkbox {...register("disclosure_required")} defaultChecked />
        Require paid-partnership disclosure
      </label>
      {serverError ? <Alert tone="danger">{serverError}</Alert> : null}
      <Button type="submit" disabled={isSubmitting} size="lg">
        {isSubmitting ? "Creating…" : "Create campaign"}
      </Button>
    </form>
  );
}
