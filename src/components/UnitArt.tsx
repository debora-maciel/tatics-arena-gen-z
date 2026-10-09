import Image from "next/image";
import type { CSSProperties } from "react";
import type { UnitDef } from "@/game/types";

/** Which render to show. `east`/`west` are the direction the character faces. */
export type ArtView = "portrait" | "board" | "front" | "back" | "east" | "west";

const FACINGS: ArtView[] = ["front", "back", "east", "west"];

interface Props {
  def: UnitDef;
  view: ArtView;
  /** Size classes for the image (e.g. "h-10 w-10"). */
  className?: string;
  /** Text size classes for the emoji fallback. */
  emojiClass?: string;
  /** Inline size (e.g. a projected arena's per-row pixel size); overrides the size classes. */
  style?: CSSProperties;
  /** Draws a white outline that follows the character's silhouette (see .art-selected in globals.css). */
  selected?: boolean;
}

function Art({ def, view, className, style, hidden = false, glow = true }: { def: UnitDef; view: ArtView; className: string; style?: CSSProperties; hidden?: boolean; glow?: boolean }) {
  return (
    <Image
      src={`${def.art}/${view}.png`}
      alt={def.name}
      width={256}
      height={256}
      sizes="160px"
      draggable={false}
      unoptimized
      hidden={hidden}
      style={style}
      className={`pointer-events-none max-w-none select-none object-contain ${glow ? "drop-shadow-[0_0_6px_rgba(255,255,255,0.35)]" : ""} ${className}`}
    />
  );
}

/** Round thumbnail for units that have a single photo instead of directional renders. */
function Photo({ def, className, style }: { def: UnitDef; className: string; style?: CSSProperties }) {
  return (
    <Image
      src={def.photo!}
      alt={def.name}
      width={256}
      height={256}
      sizes="160px"
      draggable={false}
      unoptimized
      style={style}
      className={`pointer-events-none select-none rounded-full object-cover ring-2 ring-white/70 shadow-md ${className}`}
    />
  );
}

/** A unit's picture, falling back to its emoji when the unit has no art folder. */
export function UnitArt({ def, view, className = "h-10 w-10", emojiClass = "text-2xl", style, selected = false }: Props) {
  // Selected units get the silhouette outline and grow a little so they stand out from the row.
  // The outline filter sits on a padded wrapper (padding cancelled by the negative margin) so it
  // has room to render, and the image's own soft glow is turned off while selected: chained
  // drop-shadows would otherwise amplify that faint halo into a solid blob.
  const sel = selected ? "art-selected scale-125" : "";
  return (
    <span className={`-m-3 inline-flex p-3 transition-transform ${sel}`}>
      {def.photo && (!def.art || view === "portrait") ? (
        <Photo def={def} className={className} style={style} />
      ) : def.art ? (
        <Art def={def} view={view} className={className} style={style} glow={!selected} />
      ) : (
        <span className={`inline-block leading-none ${emojiClass}`}>{def.emoji}</span>
      )}
    </span>
  );
}

/**
 * Like UnitArt, but keeps every directional render mounted (only the active one visible),
 * so turning to face a new target never waits on an image request mid-fight.
 */
/** In combat, directional renders win over a photo: a unit with both shows its 3D self on the arena. */
export function UnitArtFacing({ def, view, className = "h-10 w-10", emojiClass = "text-2xl", style }: Props) {
  if (!def.art && def.photo) return <Photo def={def} className={className} style={style} />;
  if (!def.art) return <span className={`leading-none ${emojiClass}`}>{def.emoji}</span>;
  return (
    <>
      {FACINGS.map((v) => (
        <Art key={v} def={def} view={v} className={className} style={style} hidden={v !== view} />
      ))}
    </>
  );
}
