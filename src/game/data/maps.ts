/**
 * Arena backgrounds. A map with `platform` is a painted perspective scene (see ProjectedArena);
 * one without is drawn as a flat/tilted grid (see Arena), with `file` tiled under the cells or,
 * when null, a plain dark stage. New games pick from the maps in rotation (the first entry only
 * for now; the plain stage is kept as the fallback layout).
 */
import type { Quad } from "../projection";

export interface ArenaMap {
  id: string;
  name: string;
  /** Background image, or null for a plain stage. */
  file: string | null;
  /**
   * Painted perspective maps: where the floor's four corners sit in the image, as fractions of
   * its size, clockwise from top-left. The scene fills the window, the grid is
   * projected onto that quad and the bench takes the ledge one row below it.
   */
  platform?: Quad;
  /** Image width ÷ height (default 1). */
  aspect?: number;
  /** Image point (fractions) kept at the centre of the play area, and how much to enlarge the image beyond cover. */
  focus?: [number, number];
  zoom?: number;
  /** Page colours drawn behind the arena so the whole screen follows the map. */
  palette: {
    /** Deep base colour for the page background. */
    bg: string;
    /** Translucent accent for the glow behind the arena. */
    glow: string;
    /** Translucent tint for panels, so they pick up the map's hue. */
    panel: string;
  };
}

export const MAPS: ArenaMap[] = [
  {
    id: "fountain",
    name: "Dragon Fountain",
    file: "/assets/maps/tftmap.png",
    aspect: 3584 / 2240,
    platform: { tl: [0.276, 0.148], tr: [0.718, 0.144], br: [0.781, 0.688], bl: [0.21, 0.695] },
    // The floor fills half the image, so the scene is shown a little smaller than cover to leave room for the HUD.
    focus: [0.495, 0.42],
    zoom: 0.85,
    palette: { bg: "#0d1a15", glow: "rgba(163, 230, 53, 0.14)", panel: "rgba(20, 45, 35, 0.55)" },
  },
  {
    id: "convergence",
    name: "Convergence",
    file: "/assets/maps/mixboard-image.png",
    aspect: 1280 / 720,
    platform: { tl: [0.361, 0.267], tr: [0.646, 0.267], br: [0.68, 0.576], bl: [0.332, 0.576] },
    focus: [0.505, 0.44],
    zoom: 1.0,
    palette: { bg: "#0b1410", glow: "rgba(163, 230, 53, 0.14)", panel: "rgba(20, 45, 35, 0.55)" },
  },
  {
    id: "club",
    name: "Neon Club",
    file: "/assets/maps/club.png",
    platform: { tl: [0.366, 0.259], tr: [0.649, 0.258], br: [0.679, 0.454], bl: [0.327, 0.454] },
    focus: [0.505, 0.37],
    zoom: 1.12,
    palette: { bg: "#07081a", glow: "rgba(56, 189, 248, 0.16)", panel: "rgba(40, 25, 80, 0.55)" },
  },
  {
    id: "stage",
    name: "",
    file: null,
    palette: { bg: "#070a12", glow: "rgba(148, 163, 184, 0.14)", panel: "rgba(30, 41, 59, 0.55)" },
  },
];

export const MAP_BY_ID: Record<string, ArenaMap> = Object.fromEntries(MAPS.map((m) => [m.id, m]));

/** Maps new games can start on. The others stay registered (old saves, quick switching) but are not rolled. */
const ROTATION_IDS = ["fountain"];
const ROTATION = MAPS.filter((m) => ROTATION_IDS.includes(m.id));

export function randomMapId(): string {
  return ROTATION[Math.floor(Math.random() * ROTATION.length)].id;
}

/** Whether a save's map is one new games can start on; saves on a map out of rotation get a fresh one. */
export function inRotation(id: string | undefined): boolean {
  return !!id && ROTATION.some((m) => m.id === id);
}

export function getMap(id: string | undefined): ArenaMap {
  return (id && MAP_BY_ID[id]) || MAPS[0];
}
