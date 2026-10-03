import { renderToStaticMarkup } from "react-dom/server";
import {
  Eye,
  Landmark,
  MapPin,
  Trees,
  Utensils,
} from "lucide-react";
import L from "leaflet";

import type { Stop } from "@/types/plan";

const categoryIcons = {
  museum: Landmark,
  historic: Landmark,
  monument: Landmark,
  food: Utensils,
  park: Trees,
  viewpoint: Eye,
} as const;

export function getIcon(category: string | null, kind?: Stop["kind"]) {
  const isStart = kind === "start";
  const isEnd = kind === "end";
  const Icon = isStart || isEnd
    ? MapPin
    : categoryIcons[category as keyof typeof categoryIcons] ?? MapPin;
  const color = isStart ? "#047857" : isEnd ? "#b45309" : "#1d4ed8";
  const background = isStart ? "#d1fae5" : isEnd ? "#fef3c7" : "#dbeafe";

  return L.divIcon({
    className: "",
    html: renderToStaticMarkup(
      <span
        style={{
          alignItems: "center",
          background,
          border: `2px solid ${color}`,
          borderRadius: "999px 999px 999px 4px",
          boxShadow: "0 2px 8px #0f172a33",
          color,
          display: "inline-flex",
          height: 38,
          justifyContent: "center",
          transform: "rotate(-45deg)",
          width: 38,
        }}
      >
        <Icon
          aria-hidden="true"
          size={18}
          strokeWidth={2.4}
          style={{ transform: "rotate(45deg)" }}
        />
      </span>,
    ),
    iconSize: [38, 38],
    iconAnchor: [19, 36],
    popupAnchor: [0, -34],
  });
}
