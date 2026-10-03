import mockPlan from "@/data/mock_plan.json";
import { TripMapLoader } from "@/components/map/TripMapLoader";
import type { PlanResponse } from "@/types/plan";

export default function PlanPage() {
  const plan = mockPlan as PlanResponse;
  return <TripMapLoader proposal={plan.proposals[0]} />;
}
