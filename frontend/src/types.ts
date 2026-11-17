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
  kind: "image" | "video";
  license: string;
  commercial_use: "yes" | "no" | "unclear";
  aspect_ratios: string[];
  credit_cost: number;
  max_count: number;
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
  url: string;
}

export type JobStatus = "queued" | "running" | "done" | "failed";

export interface Job {
  id: string;
  status: JobStatus;
  provider: string;
  model: string;
  prompt: string;
  preset_id: string | null;
  params: { aspect_ratio: string; size: string; width: number; height: number };
  count: number;
  cost: number;
  error: string | null;
  created_at: string;
  assets: Asset[];
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
