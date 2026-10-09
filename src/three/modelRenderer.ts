/**
 * Draws GLB models onto small per-unit 2D canvases from one shared offscreen WebGL renderer.
 * `three` is imported lazily, so a game with no 3D unit on the arena never downloads it.
 * Callers get a ViewHandle; the loop runs only while views exist and the tab is visible.
 */
import { frameModel, TrackerPool, type YawTracker } from "@/game/facing";
import type * as THREE from "three";

/** Backing resolution of every view canvas; matches the 256 px PNG renders. */
export const SIZE = 256;

/**
 * Camera pose. `front` looks at the model from slightly above eye level, for the tilted arena
 * where CSS already leans the ground; `board` looks down at about 45° with a wider lens, so a
 * unit on the flat top-down arena reads as standing on the ground.
 */
export type Pose = "front" | "board";

export interface ViewHandle {
  setYaw(yaw: number): void;
  setPose(pose: Pose): void;
  dispose(): void;
}

export interface ViewOptions {
  /** Unit id. Views with the same id share a yaw tracker, so a remounted view resumes its turn. */
  id: string;
  /** Fires after the first frame is drawn (synchronously if the model is cached), and again after a
   *  lost WebGL context is restored; never on load failure. */
  onReady: () => void;
  /** Fires when the WebGL context is lost: the canvas is blank until `onReady` fires again. */
  onLost?: () => void;
  yaw?: number;
  pose?: Pose;
}

type ThreeMod = typeof import("three");

interface Engine {
  T: ThreeMod;
  renderer: THREE.WebGLRenderer;
  scene: THREE.Scene;
  cameras: Record<Pose, THREE.PerspectiveCamera>;
  loader: import("three/addons/loaders/GLTFLoader.js").GLTFLoader;
}

interface View {
  url: string;
  canvas: HTMLCanvasElement;
  ctx: CanvasRenderingContext2D | null;
  yaw: YawTracker;
  pose: Pose;
  onReady: () => void;
  onLost?: () => void;
  /** The clone placed in the scene once its template is loaded. */
  object: THREE.Group | null;
  /** Needs a draw: first frame, pose change, or context restored. Turning views are drawn regardless. */
  dirty: boolean;
  live: boolean;
}

let enginePromise: Promise<Engine | null> | null = null;
let engine: Engine | null = null;
/** Model templates by URL: a pending promise while loading, and the resolved group once ready. */
const templates = new Map<string, Promise<THREE.Group>>();
const resolved = new Map<string, THREE.Group>();
const views = new Set<View>();
const trackers = new TrackerPool();
let raf = 0;
let lastFrame = 0;
let contextLost = false;

/** Whether `url` is loaded, so a remounted view can start visible instead of flashing its PNG. */
export function isReady(url: string): boolean {
  return !contextLost && resolved.has(url);
}

async function initEngine(): Promise<Engine | null> {
  try {
    const T = await import("three");
    const { GLTFLoader } = await import("three/addons/loaders/GLTFLoader.js");
    const { MeshoptDecoder } = await import("three/addons/libs/meshopt_decoder.module.js");

    const canvas = document.createElement("canvas");
    canvas.width = SIZE;
    canvas.height = SIZE;
    const renderer = new T.WebGLRenderer({ canvas, alpha: true, antialias: true });
    renderer.setPixelRatio(1);
    renderer.setSize(SIZE, SIZE, false);
    renderer.setClearColor(0x000000, 0);
    renderer.outputColorSpace = T.SRGBColorSpace;

    const scene = new T.Scene();
    scene.add(new T.HemisphereLight(0xffffff, 0x3a4658, 1.4));
    const key = new T.DirectionalLight(0xffffff, 1.8);
    key.position.set(-1.2, 2.2, 2.4);
    scene.add(key);

    // Both cameras frame a 1-unit-tall model standing at the origin.
    // front: ~18° above eye level, tight lens, feet near the bottom of the canvas.
    const front = new T.PerspectiveCamera(28, 1, 0.1, 20);
    front.position.set(0, 1.0, 1.75);
    front.lookAt(0, 0.5, 0);
    // board: 45° down, aimed above the model's centre so the feet land ~5% above the bottom edge of
    // the canvas (the arena anchors the canvas bottom at the cell centre, where the ground shadow is).
    const board = new T.PerspectiveCamera(28, 1, 0.1, 20);
    board.position.set(0, 1.914, 1.414);
    board.lookAt(0, 0.7, 0);

    const loader = new GLTFLoader();
    loader.setMeshoptDecoder(MeshoptDecoder);

    // A lost context (sleep/wake, GPU pressure) would otherwise leave every canvas frozen or blank.
    // Views fall back to their PNG until the context comes back, then redraw.
    canvas.addEventListener("webglcontextlost", (e) => {
      e.preventDefault();
      contextLost = true;
      for (const v of views) v.onLost?.();
    });
    canvas.addEventListener("webglcontextrestored", () => {
      contextLost = false;
      for (const v of views) {
        v.dirty = true;
        if (v.object) v.onReady();
      }
      startLoop();
    });

    return { T, renderer, scene, cameras: { front, board }, loader };
  } catch (err) {
    console.warn("3D units disabled:", err);
    return null;
  }
}

function ensureEngine(): Promise<Engine | null> {
  if (!enginePromise) {
    enginePromise = initEngine().then((e) => {
      engine = e;
      return e;
    });
  }
  return enginePromise;
}

/** Loads and normalises a model once per URL. A failed load stays failed until the page reloads. */
function loadModel(url: string): Promise<THREE.Group> {
  let p = templates.get(url);
  if (!p) {
    p = ensureEngine().then(async (e) => {
      if (!e) throw new Error("WebGL unavailable");
      const gltf = await e.loader.loadAsync(url);
      const inner = gltf.scene;
      const box = new e.T.Box3().setFromObject(inner);
      const { scale, offset } = frameModel({
        min: [box.min.x, box.min.y, box.min.z],
        max: [box.max.x, box.max.y, box.max.z],
      });
      inner.scale.setScalar(scale);
      inner.position.set(...offset);
      // The outer group rotates about the model's own centre line; the inner group holds the normalisation.
      const outer = new e.T.Group();
      outer.add(inner);
      resolved.set(url, outer);
      return outer;
    });
    templates.set(url, p);
    p.catch((err) => console.warn(`3D model failed: ${url}`, err));
  }
  return p;
}

/** Warms the cache during planning so a fight starts with its models ready. */
export function preloadModel(url: string) {
  loadModel(url).catch(() => {});
}

function attach(view: View, template: THREE.Group) {
  if (!view.live || !engine) return;
  const clone = template.clone();
  clone.visible = false;
  engine.scene.add(clone);
  view.object = clone;
  if (contextLost) return; // onReady fires from the restore handler
  drawView(view, 0);
  view.onReady();
  startLoop();
}

/** Renders one view onto its canvas, advancing its turn by `dt` seconds. */
function drawView(view: View, dt: number) {
  if (!engine || contextLost || !view.object || !view.ctx) return;
  view.object.rotation.y = view.yaw.step(dt);
  view.object.visible = true;
  engine.renderer.render(engine.scene, engine.cameras[view.pose]);
  view.object.visible = false;
  view.ctx.clearRect(0, 0, SIZE, SIZE);
  view.ctx.drawImage(engine.renderer.domElement, 0, 0);
  view.dirty = false;
}

const needsFrame = (v: View) => v.object !== null && (v.dirty || !v.yaw.settled);

/** One animation frame: draw only the views that are turning or flagged dirty; idle when none are. */
function frame(now: number) {
  raf = 0;
  const dt = lastFrame ? (now - lastFrame) / 1000 : 0;
  lastFrame = now;
  let more = false;
  for (const v of views) {
    if (!needsFrame(v)) continue;
    drawView(v, dt);
    if (needsFrame(v)) more = true;
  }
  if (more && document.visibilityState === "visible") raf = requestAnimationFrame(frame);
}

/** Arms the loop if any view has work; a static planning board costs no frames at all. */
function startLoop() {
  if (raf || document.visibilityState !== "visible" || contextLost) return;
  let any = false;
  for (const v of views) if (needsFrame(v)) any = true;
  if (!any) return;
  lastFrame = 0;
  raf = requestAnimationFrame(frame);
}

if (typeof document !== "undefined") {
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") startLoop();
  });
}

/** Registers a canvas to show `url`. Until the model is ready nothing is drawn (see ViewOptions.onReady). */
export function createView(url: string, canvas: HTMLCanvasElement, { id, onReady, onLost, yaw = 0, pose = "front" }: ViewOptions): ViewHandle {
  canvas.width = SIZE;
  canvas.height = SIZE;
  const view: View = {
    url,
    canvas,
    ctx: canvas.getContext("2d"),
    yaw: trackers.get(id),
    pose,
    onReady,
    onLost,
    object: null,
    dirty: true,
    live: true,
  };
  view.yaw.set(yaw);
  views.add(view);

  const cached = resolved.get(url);
  if (cached && engine) attach(view, cached);
  else loadModel(url).then((t) => attach(view, t)).catch(() => {});

  return {
    setYaw(yaw: number) {
      view.yaw.set(yaw);
      if (!view.yaw.settled) startLoop();
    },
    setPose(pose: Pose) {
      if (view.pose === pose) return;
      view.pose = pose;
      view.dirty = true;
      startLoop();
    },
    dispose() {
      view.live = false;
      views.delete(view);
      if (view.object && engine) engine.scene.remove(view.object);
      view.object = null;
    },
  };
}
