"use client";

import { useMemo, useState } from "react";
import DeckGL from "@deck.gl/react";
import { GeoJsonLayer } from "@deck.gl/layers";
import Map from "react-map-gl/maplibre";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { FeatureCollection } from "geojson";
import type { GeoMode, LayerMetric, ScenarioProperties, TractProperties } from "@/types";
import { getColor, CROSSED_LINE, SELECTED_LINE, TARGET_LINE } from "@/lib/colorScales";
import { fmtPct2 } from "@/lib/formatters";

const OSM_STYLE = {
  version: 8 as const,
  sources: {
    osm: {
      type: "raster" as const,
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "&copy; OpenStreetMap contributors",
    },
  },
  layers: [{ id: "osm", type: "raster" as const, source: "osm", minzoom: 0, maxzoom: 19 }],
};

function pickMetricValue(
  props: TractProperties | ScenarioProperties,
  metric: LayerMetric,
  mode: GeoMode,
): number {
  const p = props as ScenarioProperties;
  if (metric === "delta" && mode !== "baseline" && typeof p.exceedance_prob_delta === "number") {
    return p.exceedance_prob_delta;
  }
  if (
    metric === "exceedance_prob" &&
    mode !== "baseline" &&
    typeof p.exceedance_prob_scenario === "number"
  ) {
    return p.exceedance_prob_scenario;
  }
  if (metric === "posterior_mean") return p.posterior_mean;
  if (metric === "wasserstein_dist") return p.wasserstein_dist ?? 0;
  if (metric === "ci_width") return (p.ci_upper_95 ?? 0) - (p.ci_lower_95 ?? 0);
  return p.exceedance_prob;
}

function desertProbForTooltip(
  props: TractProperties | ScenarioProperties,
  mode: GeoMode,
): number {
  const p = props as ScenarioProperties;
  if (mode !== "baseline" && typeof p.exceedance_prob_scenario === "number") {
    return p.exceedance_prob_scenario;
  }
  return p.exceedance_prob;
}

type Props = {
  data: FeatureCollection;
  mode: GeoMode;
  layerMetric: LayerMetric;
  selectedGeoid: string | null;
  onSelectGeoid: (geoid: string | null) => void;
  showDesertOnly: boolean;
  showTargets: boolean;
  showHook: boolean;
  disadvantageFilter: number;
  targetGeoids: Set<string>;
  hookGeoid: string;
};

export default function TransitMap({
  data,
  mode,
  layerMetric,
  selectedGeoid,
  onSelectGeoid,
  showDesertOnly,
  showTargets,
  showHook,
  disadvantageFilter,
  targetGeoids,
  hookGeoid,
}: Props) {
  const [hover, setHover] = useState<{
    x: number;
    y: number;
    tract_name: string;
    geoid: string;
    pDesert: number;
    jobs: number;
  } | null>(null);

  const layers = useMemo(
    () => [
      new GeoJsonLayer({
        id: "tracts",
        data,
        pickable: true,
        filled: true,
        stroked: true,
        getFillColor: (f: { properties: TractProperties | ScenarioProperties }) => {
          const props = f.properties;
          const q = props.disadv_quartile ?? 0;
          const passFilter = disadvantageFilter === 0 || q === disadvantageFilter;
          const v = pickMetricValue(props, layerMetric, mode);
          const c = getColor(layerMetric, v);
          const desertOk = !showDesertOnly || props.exceedance_prob >= 0.5;
          const hookHi = showHook && props.geoid === hookGeoid;
          let a = c[3];
          if (!passFilter) a = 32;
          else if (!desertOk) a = 45;
          else if (hookHi) a = 245;
          return [c[0], c[1], c[2], a] as [number, number, number, number];
        },
        getLineColor: (f: { properties: TractProperties | ScenarioProperties }) => {
          const g = f.properties.geoid;
          const sp = f.properties as ScenarioProperties;
          if (g === selectedGeoid) return SELECTED_LINE;
          if (showHook && g === hookGeoid) return [239, 68, 68, 255];
          if (mode !== "baseline" && sp.crossed_threshold) return CROSSED_LINE;
          if (showTargets && targetGeoids.has(g)) return TARGET_LINE;
          return [90, 90, 90, 90];
        },
        getLineWidth: (f: { properties: TractProperties | ScenarioProperties }) => {
          const g = f.properties.geoid;
          const sp = f.properties as ScenarioProperties;
          if (g === selectedGeoid) return 3;
          if (showHook && g === hookGeoid) return 3;
          if (mode !== "baseline" && sp.crossed_threshold) return 2;
          if (showTargets && targetGeoids.has(g)) return 2;
          return 1;
        },
        lineWidthUnits: "pixels",
        onHover: (info) => {
          if (info.object?.properties) {
            const p = info.object.properties as TractProperties;
            setHover({
              x: info.x,
              y: info.y,
              tract_name: p.tract_name,
              geoid: p.geoid,
              pDesert: desertProbForTooltip(p, mode),
              jobs: p.posterior_mean_jobs,
            });
          } else setHover(null);
        },
        onClick: (info) => {
          if (info.object?.properties?.geoid) {
            onSelectGeoid(info.object.properties.geoid);
          }
        },
        updateTriggers: {
          getFillColor: [
            layerMetric,
            mode,
            showDesertOnly,
            showTargets,
            showHook,
            disadvantageFilter,
            hookGeoid,
          ],
          getLineColor: [selectedGeoid, showTargets, mode, showHook, hookGeoid],
          getLineWidth: [selectedGeoid, showTargets, mode, showHook, hookGeoid],
        },
      }),
    ],
    [
      data,
      layerMetric,
      mode,
      selectedGeoid,
      showDesertOnly,
      showTargets,
      showHook,
      disadvantageFilter,
      targetGeoids,
      hookGeoid,
      onSelectGeoid,
    ],
  );

  return (
    <div className="relative h-full min-h-[400px] w-full bg-slate-200">
      <DeckGL
        initialViewState={{
          longitude: -116.92,
          latitude: 32.9,
          zoom: 8.35,
          pitch: 0,
          bearing: 0,
        }}
        controller
        layers={layers}
        getCursor={({ isDragging, isHovering }) =>
          isDragging ? "grabbing" : isHovering ? "pointer" : "grab"
        }
      >
        <Map mapLib={maplibregl} mapStyle={OSM_STYLE as maplibregl.StyleSpecification} reuseMaps />
      </DeckGL>
      {hover ? (
        <div
          className="pointer-events-none absolute z-20 max-w-[220px] rounded-md border border-slate-200 bg-white/95 px-2 py-1.5 text-[11px] shadow-md backdrop-blur-sm"
          style={{ left: hover.x + 12, top: hover.y + 12 }}
        >
          <div className="font-medium text-slate-800 line-clamp-2">{hover.tract_name}</div>
          <div className="font-mono text-[10px] text-slate-500">{hover.geoid}</div>
          <div className="mt-1 text-slate-700">
            P(desert): <span className="font-semibold">{fmtPct2(hover.pDesert)}</span>
          </div>
          <div className="text-slate-600">Post. mean jobs: {Math.round(hover.jobs).toLocaleString()}</div>
        </div>
      ) : null}
    </div>
  );
}
