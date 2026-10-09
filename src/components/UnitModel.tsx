"use client";

import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties } from "react";
import type { UnitDef } from "@/game/types";
import { createView, isReady, type Pose, type ViewHandle } from "@/three/modelRenderer";
import { UnitArt, type ArtView } from "./UnitArt";

interface Props {
  /** Unit id; a remounted view with the same id resumes its turn. */
  id: string;
  def: UnitDef;
  /** Continuous facing, see facingYaw. */
  yaw: number;
  /** PNG view shown until the model is ready (or if it never is): a combat facing or `board`. */
  fallbackView: ArtView;
  /** Camera angle: `front` on the tilted arena, `board` on the flat one. */
  pose: Pose;
  /** Silhouette outline + slight scale, as UnitArt does for a selected unit. */
  selected?: boolean;
  className?: string;
  emojiClass?: string;
  /** Inline size; overrides the size classes (projected arenas size units per row). */
  style?: CSSProperties;
}

/**
 * A live 3D billboard for units with `model`. It occupies exactly the slot the directional
 * PNG occupies, so every wrapper (stand, lunge, hit, hop, die) applies unchanged.
 * Shows the PNG until the first frame is drawn; if WebGL or the load fails, the PNG stays.
 */
export function UnitModel({ id, def, yaw, fallbackView, pose, selected = false, className = "h-10 w-10", emojiClass = "text-2xl", style }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const handleRef = useRef<ViewHandle | null>(null);
  const yawRef = useRef(yaw);
  // A cached model draws synchronously in the layout effect below, so a remount (the combat
  // wrappers remount on every hit, lunge and hop) starts visible instead of flashing the PNG.
  const [ready, setReady] = useState(() => !!def.model && isReady(def.model));

  // Declared before the mount effect so that on the first render the ref holds the real yaw
  // before the view is created: a cached model draws its first frame synchronously in createView.
  useEffect(() => {
    yawRef.current = yaw;
    handleRef.current?.setYaw(yaw);
  }, [yaw]);

  const poseRef = useRef(pose);
  useEffect(() => {
    poseRef.current = pose;
    handleRef.current?.setPose(pose);
  }, [pose]);

  useLayoutEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !def.model) return;
    const handle = createView(def.model, canvas, {
      id,
      onReady: () => setReady(true),
      onLost: () => setReady(false),
      yaw: yawRef.current,
      pose: poseRef.current,
    });
    handleRef.current = handle;
    return () => {
      handle.dispose();
      handleRef.current = null;
    };
  }, [id, def.model]);

  // Same padded wrapper as UnitArt: the outline filter needs room, and the glow is dropped while
  // selected so chained drop-shadows do not bloom.
  const sel = selected ? "art-selected scale-125" : "";
  return (
    <span className={`-m-3 inline-flex p-3 transition-transform ${sel}`}>
      {!ready && <UnitArt def={def} view={fallbackView} className={className} emojiClass={emojiClass} style={style} />}
      <canvas
        ref={canvasRef}
        aria-label={def.name}
        hidden={!ready}
        style={style}
        className={`pointer-events-none max-w-none select-none ${selected ? "" : "drop-shadow-[0_0_6px_rgba(255,255,255,0.35)]"} ${className}`}
      />
    </span>
  );
}
