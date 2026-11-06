/** TanStack Query hooks per API domain. */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryOptions,
} from "@tanstack/react-query";
import { useApi } from "./useApi";
import type {
  AdminUser,
  Agreement,
  Application,
  AuditLog,
  BrandPublic,
  Campaign,
  CampaignList,
  Collaboration,
  CreatorList,
  CreatorPublic,
  Deliverable,
  Dispute,
  MeProfile,
  Notification,
  Payment,
  Payout,
  PayoutMethod,
  Report,
  WebhookEvent,
} from "./types";

/** Centralised query-key factory — keep in sync when adding domains. */
export const qk = {
  me: ["me"] as const,
  profile: ["me", "profile"] as const,
  creators: (q: Record<string, unknown>) => ["creators", q] as const,
  creator: (id: string) => ["creators", id] as const,
  brand: (id: string) => ["brands", id] as const,
  campaigns: (q: Record<string, unknown>) => ["campaigns", q] as const,
  campaign: (id: string) => ["campaigns", id] as const,
  campaignApps: (id: string) => ["campaigns", id, "applications"] as const,
  myApplications: ["me", "applications"] as const,
  collaborations: ["collaborations"] as const,
  collaboration: (id: string) => ["collaborations", id] as const,
  agreement: (collabId: string) => ["collaborations", collabId, "agreement"] as const,
  deliverables: (collabId: string) =>
    ["collaborations", collabId, "deliverables"] as const,
  funding: (collabId: string) => ["collaborations", collabId, "funding"] as const,
  payment: (collabId: string) => ["collaborations", collabId, "payment"] as const,
  payout: (collabId: string) => ["collaborations", collabId, "payout"] as const,
  payoutMethod: ["me", "payout-method"] as const,
  notifications: ["me", "notifications"] as const,
  adminUsers: ["admin", "users"] as const,
  adminCampaigns: ["admin", "campaigns"] as const,
  adminCollaborations: ["admin", "collaborations"] as const,
  adminReports: ["admin", "reports"] as const,
  adminDisputes: ["admin", "disputes"] as const,
  adminPaymentEvents: ["admin", "payment-events"] as const,
  adminAuditLogs: ["admin", "audit-logs"] as const,
} as const;

// ---------------------------------------------------------------------------
// Profile
// ---------------------------------------------------------------------------

export function useMyProfile(
  opts?: Omit<UseQueryOptions<MeProfile>, "queryKey" | "queryFn">,
) {
  const api = useApi();
  return useQuery<MeProfile>({
    queryKey: qk.profile,
    queryFn: () => api.get<MeProfile>("/me/profile"),
    ...opts,
  });
}

export function useUpdateProfile() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (patch: Record<string, unknown>) =>
      api.patch<MeProfile>("/me/profile", { body: patch }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.profile }),
  });
}

// ---------------------------------------------------------------------------
// Creators (public)
// ---------------------------------------------------------------------------

export function useCreators(
  query: {
    niche?: string;
    content_type?: string;
    language?: string;
    location?: string;
    campaign_type_capability?: "ugc" | "influencer" | "hybrid";
    page?: number;
    page_size?: number;
  } = {},
) {
  const api = useApi();
  return useQuery<CreatorList>({
    queryKey: qk.creators(query),
    queryFn: () => api.get<CreatorList>("/creators", { query }),
  });
}

export function useCreator(id: string) {
  const api = useApi();
  return useQuery<CreatorPublic>({
    queryKey: qk.creator(id),
    queryFn: () => api.get<CreatorPublic>(`/creators/${id}`),
    enabled: Boolean(id),
  });
}

export function usePublicBrand(id: string) {
  const api = useApi();
  return useQuery<BrandPublic>({
    queryKey: qk.brand(id),
    queryFn: () => api.get<BrandPublic>(`/brands/${id}/public`),
    enabled: Boolean(id),
  });
}

// ---------------------------------------------------------------------------
// Campaigns
// ---------------------------------------------------------------------------

export function useCampaigns(
  query: {
    niche?: string;
    type?: string;
    language?: string;
    location?: string;
    budget_min?: number;
    budget_max?: number;
    page?: number;
    page_size?: number;
  } = {},
) {
  const api = useApi();
  return useQuery<CampaignList>({
    queryKey: qk.campaigns(query),
    queryFn: () => api.get<CampaignList>("/campaigns", { query }),
  });
}

export function useCampaign(id: string) {
  const api = useApi();
  return useQuery<Campaign>({
    queryKey: qk.campaign(id),
    queryFn: () => api.get<Campaign>(`/campaigns/${id}`),
    enabled: Boolean(id),
  });
}

export function useCreateCampaign() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post<Campaign>("/campaigns", { body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["campaigns"] }),
  });
}

// ---------------------------------------------------------------------------
// Applications
// ---------------------------------------------------------------------------

export function useCampaignApplications(campaignId: string) {
  const api = useApi();
  return useQuery<Application[]>({
    queryKey: qk.campaignApps(campaignId),
    queryFn: () =>
      api.get<Application[]>(`/campaigns/${campaignId}/applications`),
    enabled: Boolean(campaignId),
  });
}

export function useMyApplications() {
  const api = useApi();
  return useQuery<Application[]>({
    queryKey: qk.myApplications,
    queryFn: () => api.get<Application[]>("/me/applications"),
  });
}

export function useAcceptApplication() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (applicationId: string) =>
      api.post<{ application: Application; collaboration_id: string }>(
        `/applications/${applicationId}/accept`,
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["campaigns"] });
      qc.invalidateQueries({ queryKey: qk.collaborations });
    },
  });
}

export function useRejectApplication() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (applicationId: string) =>
      api.post<Application>(`/applications/${applicationId}/reject`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["campaigns"] }),
  });
}

export function useWithdrawApplication() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (applicationId: string) =>
      api.post<Application>(`/applications/${applicationId}/withdraw`),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.myApplications }),
  });
}

export function useSubmitApplication(campaignId: string) {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post<Application>(`/campaigns/${campaignId}/applications`, { body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.myApplications }),
  });
}

// ---------------------------------------------------------------------------
// Collaborations
// ---------------------------------------------------------------------------

export function useCollaborations() {
  const api = useApi();
  return useQuery<Collaboration[]>({
    queryKey: qk.collaborations,
    queryFn: () => api.get<Collaboration[]>("/collaborations"),
  });
}

export function useCollaboration(id: string) {
  const api = useApi();
  return useQuery<Collaboration>({
    queryKey: qk.collaboration(id),
    queryFn: () => api.get<Collaboration>(`/collaborations/${id}`),
    enabled: Boolean(id),
  });
}

export function useAgreement(collabId: string) {
  const api = useApi();
  return useQuery<Agreement>({
    queryKey: qk.agreement(collabId),
    queryFn: () => api.get<Agreement>(`/collaborations/${collabId}/agreement`),
    enabled: Boolean(collabId),
  });
}

export function useSignAgreement() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (agreementId: string) =>
      api.post<Agreement>(`/agreements/${agreementId}/sign`),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["collaborations"] }),
  });
}

// ---------------------------------------------------------------------------
// Deliverables
// ---------------------------------------------------------------------------

export function useDeliverables(collabId: string) {
  const api = useApi();
  return useQuery<Deliverable[]>({
    queryKey: qk.deliverables(collabId),
    queryFn: () =>
      api.get<Deliverable[]>(`/collaborations/${collabId}/deliverables`),
    enabled: Boolean(collabId),
  });
}

export function useSubmitDeliverable(collabId: string) {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post<Deliverable>(`/collaborations/${collabId}/deliverables`, {
        body,
      }),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: qk.deliverables(collabId) }),
  });
}

export function useApproveDeliverable(collabId: string) {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (deliverableId: string) =>
      api.post<unknown>(`/deliverables/${deliverableId}/approve`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.deliverables(collabId) });
      qc.invalidateQueries({ queryKey: qk.collaboration(collabId) });
      qc.invalidateQueries({ queryKey: qk.payout(collabId) });
    },
  });
}

export function useRequestRevision(collabId: string) {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ deliverableId, note }: { deliverableId: string; note: string }) =>
      api.post<Deliverable>(`/deliverables/${deliverableId}/request-revision`, {
        body: { note },
      }),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: qk.deliverables(collabId) }),
  });
}

export function useOpenDispute(collabId: string) {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (reason: string) =>
      api.post<Dispute>(`/collaborations/${collabId}/disputes`, {
        body: { reason },
      }),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: qk.collaboration(collabId) }),
  });
}

// ---------------------------------------------------------------------------
// Payments / Payouts
// ---------------------------------------------------------------------------

export function useFunding(collabId: string) {
  const api = useApi();
  return useQuery<{
    collaboration_id: string;
    funding_status: string;
    collaboration_status: string;
  }>({
    queryKey: qk.funding(collabId),
    queryFn: () =>
      api.get(`/collaborations/${collabId}/funding`),
    enabled: Boolean(collabId),
  });
}

export function usePayment(collabId: string) {
  const api = useApi();
  return useQuery<Payment>({
    queryKey: qk.payment(collabId),
    queryFn: () => api.get<Payment>(`/collaborations/${collabId}/payment`),
    enabled: Boolean(collabId),
  });
}

export function usePayout(collabId: string) {
  const api = useApi();
  return useQuery<Payout>({
    queryKey: qk.payout(collabId),
    queryFn: () => api.get<Payout>(`/collaborations/${collabId}/payouts`),
    enabled: Boolean(collabId),
  });
}

export function useInitiateFunding() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (collabId: string) =>
      api.post<Payment>(`/collaborations/${collabId}/funding`),
    onSuccess: (_data, collabId) => {
      qc.invalidateQueries({ queryKey: qk.funding(collabId) });
      qc.invalidateQueries({ queryKey: qk.payment(collabId) });
      qc.invalidateQueries({ queryKey: qk.collaboration(collabId) });
    },
  });
}

export function useCreatePayout() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (collabId: string) =>
      api.post<Payout>(`/collaborations/${collabId}/payouts`),
    onSuccess: (_data, collabId) => {
      qc.invalidateQueries({ queryKey: qk.payout(collabId) });
      qc.invalidateQueries({ queryKey: qk.collaboration(collabId) });
    },
  });
}

// ---------------------------------------------------------------------------
// Payout methods
// ---------------------------------------------------------------------------

export function useMyPayoutMethod() {
  const api = useApi();
  return useQuery<PayoutMethod | null>({
    queryKey: qk.payoutMethod,
    queryFn: async () => {
      try {
        return await api.get<PayoutMethod>("/me/payout-method");
      } catch (e) {
        if (
          typeof e === "object" &&
          e &&
          "status" in e &&
          (e as { status: number }).status === 404
        ) {
          return null;
        }
        throw e;
      }
    },
  });
}

export function useSavePayoutMethod() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.put<PayoutMethod>("/me/payout-method", { body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.payoutMethod }),
  });
}

// ---------------------------------------------------------------------------
// Notifications
// ---------------------------------------------------------------------------

export function useNotifications() {
  const api = useApi();
  return useQuery<Notification[]>({
    queryKey: qk.notifications,
    queryFn: () => api.get<Notification[]>("/me/notifications"),
  });
}

export function useMarkNotificationRead() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      api.post<Notification>(`/me/notifications/${id}/read`),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.notifications }),
  });
}

// ---------------------------------------------------------------------------
// Admin
// ---------------------------------------------------------------------------

export function useAdminUsers() {
  const api = useApi();
  return useQuery<AdminUser[]>({
    queryKey: qk.adminUsers,
    queryFn: () => api.get<AdminUser[]>("/admin/users"),
  });
}

export function useAdminCampaigns() {
  const api = useApi();
  return useQuery<Campaign[]>({
    queryKey: qk.adminCampaigns,
    queryFn: () => api.get<Campaign[]>("/admin/campaigns"),
  });
}

export function useAdminCollaborations() {
  const api = useApi();
  return useQuery<Collaboration[]>({
    queryKey: qk.adminCollaborations,
    queryFn: () => api.get<Collaboration[]>("/admin/collaborations"),
  });
}

export function useAdminReports() {
  const api = useApi();
  return useQuery<Report[]>({
    queryKey: qk.adminReports,
    queryFn: () => api.get<Report[]>("/admin/reports"),
  });
}

export function useAdminDisputes() {
  const api = useApi();
  return useQuery<Dispute[]>({
    queryKey: qk.adminDisputes,
    queryFn: () => api.get<Dispute[]>("/admin/disputes"),
  });
}

export function useAdminPaymentEvents() {
  const api = useApi();
  return useQuery<WebhookEvent[]>({
    queryKey: qk.adminPaymentEvents,
    queryFn: () => api.get<WebhookEvent[]>("/admin/payment-events"),
  });
}

export function useAdminAuditLogs() {
  const api = useApi();
  return useQuery<AuditLog[]>({
    queryKey: qk.adminAuditLogs,
    queryFn: () => api.get<AuditLog[]>("/admin/audit-logs"),
  });
}

export function useDeactivateUser() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) =>
      api.post<AdminUser>(`/admin/users/${userId}/deactivate`),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.adminUsers }),
  });
}

export function useArchiveCampaign() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (campaignId: string) =>
      api.post<Campaign>(`/admin/campaigns/${campaignId}/archive`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.adminCampaigns });
      qc.invalidateQueries({ queryKey: ["campaigns"] });
    },
  });
}

export function useReviewReport() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      status,
    }: {
      id: string;
      status: "reviewed" | "dismissed";
    }) =>
      api.post<Report>(`/admin/reports/${id}/review`, {
        body: { status },
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.adminReports }),
  });
}

export function useResolveDispute() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      resolution,
      split_bps,
    }: {
      id: string;
      resolution: "release_to_creator" | "refund_to_brand" | "split";
      split_bps?: number;
    }) =>
      api.post<Dispute>(`/admin/disputes/${id}/resolve`, {
        body: {
          resolution,
          ...(split_bps !== undefined ? { split_bps } : {}),
        },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.adminDisputes });
      qc.invalidateQueries({ queryKey: qk.adminCollaborations });
    },
  });
}
