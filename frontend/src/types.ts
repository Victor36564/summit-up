export type Trail = {
  place_id: string;
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
export type SavedTrail = Trail & { id?: number; metrics?: Metrics | null };
