/** Shared response types mirrored from the backend Pydantic schemas. */

export type Role = "creator" | "brand" | "admin";

export interface MeResponse {
  user_id: string;
  email: string;
  role: Role;
}

export interface LoginResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user: MeResponse;
}

export interface CreatorPublic {
  id: string;
  display_name: string | null;
  avatar_file_id: string | null;
  bio: string | null;
  city: string | null;
  state: string | null;
  languages: string[];
  niches: string[];
  does_ugc: boolean;
  does_influencer: boolean;
  content_types: string[];
  starting_rate_paise: number | null;
  currency: string;
  portfolio_links: { label: string; url: string }[];
  social_handles: {
    platform: string;
    handle: string;
    follower_count?: number;
    unverified: true;
  }[];
}

export interface CreatorList {
  items: CreatorPublic[];
  page: number;
  page_size: number;
  total: number;
}

export interface Campaign {
  id: string;
  brand_id: string;
  title: string;
  description: string | null;
  type: "ugc" | "influencer" | "hybrid";
  niches: string[];
  platforms: string[];
  languages: string[];
  locations: string[];
  budget_paise: number;
  currency: string;
  number_of_creators: number;
  deliverable_spec: Record<string, unknown>[];
  submission_deadline: string | null;
  revision_limit: number;
  usage_rights: string | null;
  disclosure_required: boolean;
  eligibility_filters: Record<string, unknown>;
  status: "draft" | "open" | "closed" | "archived";
  created_at: string;
  updated_at: string;
}

export interface CampaignList {
  items: Campaign[];
  page: number;
  page_size: number;
  total: number;
}

export interface Application {
  id: string;
  campaign_id: string;
  creator_id: string;
  proposed_price_paise: number | null;
  currency: string;
  pitch: string | null;
  portfolio_links: Record<string, unknown>[];
  status:
    | "invited"
    | "submitted"
    | "shortlisted"
    | "accepted"
    | "rejected"
    | "withdrawn";
  invited_by_brand: boolean;
  created_at: string;
  updated_at: string;
}

export interface Collaboration {
  id: string;
  campaign_id: string;
  application_id: string;
  brand_id: string;
  creator_id: string;
  status: string;
  price_paise: number;
  currency: string;
  funding_status: string;
  payout_status: string;
  created_at: string;
  updated_at: string;
}

export interface Agreement {
  id: string;
  collaboration_id: string;
  version_number: number;
  scope: string | null;
  deliverable_spec: Record<string, unknown>[];
  price_paise: number;
  currency: string;
  deadline: string | null;
  revision_limit: number;
  usage_rights: string | null;
  disclosure_required: boolean;
  brand_signed_at: string | null;
  creator_signed_at: string | null;
  superseded_at: string | null;
}

export interface Deliverable {
  id: string;
  collaboration_id: string;
  spec_index: number;
  kind: "file" | "link";
  file_id: string | null;
  external_url: string | null;
  caption: string | null;
  status: "submitted" | "revision_requested" | "approved" | "disputed";
  revision_count: number;
  created_at: string;
  updated_at: string;
}

export interface Payment {
  id: string;
  collaboration_id: string;
  kind: "funding";
  provider: string;
  provider_order_id: string;
  amount_paise: number;
  currency: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface Payout {
  id: string;
  collaboration_id: string;
  provider: string;
  provider_payout_id: string | null;
  amount_paise: number;
  currency: string;
  status: "pending" | "processing" | "paid" | "failed";
  beneficiary_snapshot: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface PayoutMethod {
  id: string;
  method: "upi" | "bank";
  label: string | null;
  holder_name: string;
  account_number_last4: string | null;
  upi_vpa_masked: string | null;
  verified: boolean;
}

export interface Notification {
  id: string;
  type: string;
  payload: Record<string, unknown>;
  read_at: string | null;
  created_at: string;
}

export interface Dispute {
  id: string;
  collaboration_id: string;
  opened_by_user_id: string | null;
  reason: string;
  status: "open" | "resolved" | "rejected";
  resolution: "release_to_creator" | "refund_to_brand" | "split" | null;
  split_bps: number | null;
  resolved_by_admin_id: string | null;
  resolved_at: string | null;
  created_at: string;
}

export interface Report {
  id: string;
  reporter_user_id: string | null;
  target_type: "user" | "campaign";
  target_id: string;
  reason: string;
  status: "open" | "reviewed" | "dismissed";
  created_at: string;
}

export interface AdminUser {
  id: string;
  email: string;
  role: Role;
  is_active: boolean;
  created_at: string;
}

export interface AuditLog {
  id: string;
  actor_user_id: string | null;
  action: string;
  target_type: string;
  target_id: string | null;
  diff: Record<string, unknown>;
  occurred_at: string;
}

export interface WebhookEvent {
  id: string;
  provider: string;
  provider_event_id: string;
  event_type: string;
  verified: boolean;
  processed_at: string | null;
  created_at: string;
}

export interface CreatorProfileSelf {
  id: string;
  user_id: string;
  display_name: string | null;
  avatar_file_id: string | null;
  bio: string | null;
  city: string | null;
  state: string | null;
  languages: string[];
  niches: string[];
  does_ugc: boolean;
  does_influencer: boolean;
  content_types: string[];
  starting_rate_paise: number | null;
  currency: string;
  portfolio_links: { label: string; url: string }[];
  social_handles: {
    platform: string;
    handle: string;
    follower_count?: number | null;
    unverified?: boolean;
  }[];
  is_onboarded: boolean;
}

export interface BrandProfileSelf {
  id: string;
  user_id: string;
  company_name: string | null;
  website: string | null;
  logo_file_id: string | null;
  industry: string | null;
  contact_name: string | null;
  contact_email: string | null;
  gstin: string | null;
  billing_address: {
    line1?: string;
    line2?: string | null;
    city?: string;
    state?: string;
    postal_code?: string;
    country?: string;
  };
  description: string | null;
  is_onboarded: boolean;
}

export interface MeProfile {
  role: Role | null;
  creator?: CreatorProfileSelf | null;
  brand?: BrandProfileSelf | null;
}
