"use client";

import { useRouter } from "next/navigation";
import { CampaignCreateForm } from "@/components/forms/CampaignCreateForm";
import { useCreateCampaign } from "@/lib/api/queries";
import { useToast } from "@/components/ui/toast";

export default function BrandNewCampaignPage() {
  const router = useRouter();
  const create = useCreateCampaign();
  const { push } = useToast();
  return (
    <div className="mx-auto flex max-w-xl flex-col gap-6">
      <h1 className="text-2xl font-bold">New campaign</h1>
      <CampaignCreateForm
        onSubmit={async (payload) => {
          const created = await create.mutateAsync(payload);
          push({ title: "Campaign created", tone: "success" });
          router.push(`/brand/campaigns/${created.id}`);
        }}
      />
    </div>
  );
}
