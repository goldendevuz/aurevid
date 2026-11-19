// SPDX-License-Identifier: AGPL-3.0-or-later
export type Locale = "en" | "uz" | "ru";

export interface User {
  id: string;
  email: string;
  locale: Locale;
  is_admin: boolean;
  credit_balance: number;
  created_at: string;
}

export interface ModelInfo {
  id: string;
  label: string;
  kind: "image" | "video" | "upscale";
  license: string;
  commercial_use: "yes" | "no" | "unclear";
  aspect_ratios: string[];
  credit_cost: number;
  max_count: number;
  durations: number[];
  accepts_image: boolean;
  requires_image: boolean;
  has_audio?: boolean;
  upscale_targets: ("4k" | "8k")[];
  upscale_credits: Record<string, number>;
}

export interface QuotaView {
  used_today: number;
  estimated_limit: number | null;
  remaining: number | null;
  source: "documented" | "learned" | "unknown";
  observations: number;
  blocked_seconds: number;
}

export interface Provider {
  id: string;
  name: string;
  tier: "free" | "paid";
  byok: boolean;
  byok_fields: string[];
  requires_key: boolean;
  models: ModelInfo[];
  notes: string;
  available: boolean;
  key_source: "server" | "user" | "none";
  key_url: string;
  key_guide_url: string;
  quota: QuotaView | null;
  free_left: number | null; // free outputs left on the Aurevid key
}

export interface Preset {
  id: string;
  name: string;
  category: string;
  description: string;
  image_defaults: { aspect_ratio?: string };
}

export interface Asset {
  id: string;
  job_id: string | null;
  mime: string;
  width: number;
  height: number;
  is_favorite: boolean;
  alt_text?: string | null; // machine-written description (Cloudflare image-to-text)
  url: string;
  preview_url: string;
}

/** Chain state stored on each job of a recipe (see backend services/recipes.py). */
export interface RecipeState {
  id: string;
  next?: { provider: string; model: string; duration: number | null; upscale: "4k" | "8k" | null }[];
  next_job_id?: string;
  prev_job_id?: string;
  error?: string;
}

export type JobStatus = "queued" | "running" | "done" | "failed";

export interface Job {
  id: string;
  kind: "image" | "video";
  status: JobStatus;
  provider: string;
  model: string;
  prompt: string;
  preset_id: string | null;
  params: {
    aspect_ratio: string;
    size: string;
    width: number;
    height: number;
    duration?: number | null;
    image_asset_id?: string | null;
    upscale?: "4k" | "8k" | null;
    seed?: number | null;
    source_asset_id?: string | null;
    recipe?: RecipeState;
  };
  count: number;
  cost: number;
  error: string | null;
  created_at: string;
  started_at?: string | null;
  assets: Asset[];
  queue_position?: number | null;
  eta_seconds?: number | null;
  typical_seconds?: number | null;
  model_label?: string | null;
  provider_name?: string | null;
  has_audio?: boolean;
}

export interface Usage {
  balance: number;
  jobs_today: number;
  daily_job_limit: number;
  ledger: { id: string; delta: number; reason: string; balance_after: number; created_at: string }[];
}

export interface ProviderKeyStatus {
  provider: string;
  configured: boolean;
  updated_at: string | null;
}

export interface Facet {
  value: string;
  count: number;
  label?: string | null;
  provider?: string | null;
}

export interface JobFacets {
  total: number;
  kinds: Facet[];
  statuses: Facet[];
  providers: Facet[];
  models: Facet[];
}

export interface CreditPack {
  id: string;
  credits: number;
  amount_uzs: number;
}

export interface CreditPacks {
  enabled: boolean;
  packs: CreditPack[];
}

export type PaymentStatus = "created" | "pending" | "paid" | "failed" | "expired";

export interface PaymentOrder {
  id: string;
  pack_id: string;
  credits: number;
  amount_uzs: number;
  status: PaymentStatus;
  created_at: string;
  paid_at: string | null;
}
