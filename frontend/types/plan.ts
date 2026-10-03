export type Mode = "walk" | "bus" | "bike" | "scooter" | "taxi" | "car";
export type Strategy = "cheapest" | "fastest" | "most_sights" | "least_crowded";

export interface Place {
  id?: string | null;
  name: string;
  lat: number;
  lng: number;
  category: string | null;
  district?: string | null;
  address?: string | null;
  crowd_level?: "low" | "medium" | "high" | null;
  sponsored?: boolean;
}

export interface Stop {
  id: string;
  order: number;
  kind: "start" | "attraction" | "end";
  place: Place;
  arrival_at: string | null;
  departure_at: string | null;
  visit_duration_min: number;
  price_pln: number;
}

export interface Leg {
  id: string;
  from_stop_id: string;
  to_stop_id: string;
  mode: Mode;
  distance_m: number;
  duration_min: number;
  cost_pln: number;
  coords: [number, number][];
}

export interface Summary {
  total_cost_pln: number;
  total_duration_min: number;
  total_distance_m: number;
  total_walking_m: number;
  attractions_count: number;
  fits_time: boolean;
  fits_budget: boolean;
  time_over_min: number;
  budget_over_pln: number;
}

export interface PlanWarning {
  code: string;
  message: string;
  stop_id: string | null;
}

export interface Proposal {
  label: "A" | "B" | "C" | "D";
  strategy: Strategy;
  title: string;
  summary: Summary;
  stops: Stop[];
  legs: Leg[];
  warnings: PlanWarning[];
}

export interface PlanResponse {
  request_id: string;
  proposals: Proposal[];
  weather: {
    checked: boolean;
    condition: string;
    temp_c: number;
    affected_stop_ids: string[];
  } | null;
}
