export type Trail = {
  place_id: string | null;
  name: string;
  address?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  rating?: number | null;
  user_rating_count?: number | null;
  video_id?: string | null;
};

export type Video = {
  video_id: string;
  title: string;
  duration_sec: number;
  dimensions: string;
  tags: string[];
  description: string;
  url: string;
  hike_names: string[];
};
export type VideoComment = { author: string; text: string; like_count: number; published_at?: string | null };

export type Metrics = {
  name: string;
  area_name?: string | null;
  city?: string | null;
  state?: string | null;
  length_miles?: number | null;
  length_km?: number | null;
  elevation_gain_feet?: number | null;
  elevation_gain_meters?: number | null;
  difficulty?: string | null;
  route_type?: string | null;
  available: boolean;
};

export type Review = { author: string; rating?: number | null; relative_time?: string | null; text: string };
export type Details = Trail & { website_uri?: string | null; opening_hours: string[]; reviews: Review[]; photos: string[] };
export type Personalization = {
  status: "cold_start" | "personalized" | "unusable_profile" | "disabled";
  saved_examples_used: number;
  saved_catalog_hike_ids?: string[];
  saved_catalog_count?: number;
  external_saved_count?: number;
  unresolved_saved_ids?: string[];
  matching_methods?: string[];
  model_category?: string;
  model_id?: string;
  revision?: string;
  profile_method?: string;
  catalog_text_status?: string;
  rank_quality_validated?: boolean;
};
export type SavedTrail = Trail & { id?: number | null; catalog_hike_id?: string | null; metrics?: Metrics | null };
export type CatalogSave = { catalog_hike_id: string; name: string; address?: string | null; latitude?: number | null; longitude?: number | null; metrics?: Metrics | null };

export type RecommendationRequest = {
  travel_date: string;
  as_of?: string;
  region?: string;
  difficulty?: string;
  max_distance_km?: number;
  max_elevation_gain_m?: number;
  max_time_hours?: number;
  preferences_text?: string;
  desired_features?: string[];
  condition_weights?: Record<string, number>;
  allow_experimental: true;
  personalization_weight?: number;
  exclude_saved?: boolean;
  top_k?: number;
};
export type RecommendationCondition = { model_score: number | null; status: string; used_in_ranking: boolean };
export type SimilarSavedHike = { hike_id: string; name: string };
export type RecommendationResult = {
  personalization_score: number | null;
  personalization_used: boolean;
  similar_saved_hike: SimilarSavedHike | null;
  hike_id: string;
  name: string;
  region: string;
  distance_km: number | null;
  elevation_gain_m: number | null;
  estimated_time_hours: string | null;
  difficulty: string | null;
  ranking_score: number | null;
  seasonal_suitability_score: number | null;
  text_similarity: number | null;
  conditions: Record<string, RecommendationCondition>;
  unsupported_weighted_targets: string[];
  unknown_requested_features: string[];
  same_hike_month_observations: number | null;
  climate_scope: string | null;
  source_url: string | null;
  reasons: string[];
  rank: number | null;
};
export type BaseRecommendationResponse = {
  personalization?: Personalization;
  status?: "experimental" | "limited_evidence" | "no_matches";
  results?: RecommendationResult[];
  request?: Record<string, unknown>;
  travel_date?: string;
  as_of?: string;
  text_backend?: string;
  candidates?: number;
  prediction_meaning?: string;
  ranking_validated?: boolean;
};
export type RecommendationResponse =
  | (BaseRecommendationResponse & { status: "experimental" | "limited_evidence"; travel_date: string; as_of: string; text_backend: string; candidates: number; prediction_meaning: string; ranking_validated: boolean; results: RecommendationResult[] })
  | (BaseRecommendationResponse & { status: "no_matches"; results: RecommendationResult[]; request: Record<string, unknown> });
export type RecommendationOptions = { regions: string[]; difficulties: string[] };
