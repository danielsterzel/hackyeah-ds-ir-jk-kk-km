export type Mode = "walk" | "bus" | "bike" | "scooter" | "taxi" | "car";
export type Strategy = "cheapest" | "fastest" | "most_places" | "least_crowded";
export type SolverStatus =
  | "optimal"
  | "feasible"
  | "infeasible"
  | "timeout"
  | "error";

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
  opens_at: string | null;
  closes_at: string | null;
  warnings: PlanWarning[];
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
  fits_budget: boolean | null;
  time_over_min: number;
  budget_over_pln: number | null;
}

export interface PlanWarning {
  code: string;
  message: string;
  stop_id: string | null;
  leg_id: string | null;
}

export interface RoutePlan {
  strategy: Strategy;
  solver_status: SolverStatus;
  objective_value: number | null;
  total_reward: number;
  summary: Summary;
  stops: Stop[];
  legs: Leg[];
  warnings: PlanWarning[];
  skipped_poi_ids: string[];
}

export interface PlanResponse {
  request_id: string;
  plan: RoutePlan;
  weather: {
    checked: boolean;
    condition: string;
    temp_c: number;
    affected_stop_ids: string[];
  } | null;
}
