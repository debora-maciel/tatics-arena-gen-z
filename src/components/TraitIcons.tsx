import type { ReactNode } from "react";
import type { Trait } from "@/game/types";

/**
 * One icon per origin and role, Phosphor-style strokes on a 256 viewBox using currentColor.
 * The same drawings are saved as files in public/assets/icons/<trait>.svg.
 */
const PATHS: Record<Trait, ReactNode> = {
  Forest: (
    <>
      <path d="M128,24 L64,120 H100 L48,192 H208 L156,120 H192 Z" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="16"/><line x1="128" y1="192" x2="128" y2="232" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="16"/>
    </>
  ),
  Ember: (
    <>
      <path d="M128,232c-40,0-72-30-72-72c0-44,32-70,48-100c8,24,20,40,36,48c0-24,8-44,24-60c8,40,36,66,36,112C200,202,168,232,128,232Z" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="16"/><path d="M128,232c-18,0-32-14-32-32c0-20,16-30,24-48c8,12,16,20,24,24c8,8,16,14,16,24C160,218,146,232,128,232Z" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="16"/>
    </>
  ),
  Tide: (
    <>
      <path d="M24,80c24-24,48-24,72,0s48,24,72,0s40-24,64,0" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="16"/><path d="M24,136c24-24,48-24,72,0s48,24,72,0s40-24,64,0" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="16"/><path d="M24,192c24-24,48-24,72,0s48,24,72,0s40-24,64,0" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="16"/>
    </>
  ),
  Storm: (
    <>
      <polygon points="160 16 144 96 208 120 96 240 112 160 48 136 160 16" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="16"/>
    </>
  ),
  Void: (
    <>
      <circle cx="128" cy="128" r="80" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="16"/><circle cx="128" cy="128" r="28" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="16"/><line x1="128" y1="16" x2="128" y2="40" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="16"/><line x1="128" y1="216" x2="128" y2="240" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="16"/><line x1="16" y1="128" x2="40" y2="128" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="16"/><line x1="216" y1="128" x2="240" y2="128" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="16"/>
    </>
  ),
  Iron: (
    <>
      <polygon points="128 24 218 76 218 180 128 232 38 180 38 76" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="16"/><circle cx="128" cy="128" r="36" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="16"/>
    </>
  ),
  Warrior: (
    <>
      <line x1="216" y1="40" x2="104" y2="152" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="16"/><polyline points="216 40 216 88 168 88" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="16"/><line x1="80" y1="128" x2="128" y2="176" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="16"/><line x1="104" y1="152" x2="48" y2="208" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="16"/>
    </>
  ),
  Ranger: (
    <>
      <path d="M64,40c88,0,152,64,152,152" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="16"/><line x1="64" y1="40" x2="216" y2="192" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="16"/><line x1="40" y1="216" x2="168" y2="88" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="16"/><polyline points="128 88 168 88 168 128" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="16"/>
    </>
  ),
  Mage: (
    <>
      <line x1="40" y1="216" x2="168" y2="88" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="16"/><line x1="192" y1="24" x2="192" y2="104" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="16"/><line x1="152" y1="64" x2="232" y2="64" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="16"/><line x1="64" y1="72" x2="64" y2="112" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="16"/><line x1="44" y1="92" x2="84" y2="92" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="16"/>
    </>
  ),
  Guardian: (
    <>
      <path d="M40,56V120c0,64,40,104,88,120c48-16,88-56,88-120V56Z" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="16"/><polyline points="88 128 116 156 168 104" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="16"/>
    </>
  ),
  Assassin: (
    <>
      <path d="M128,24L160,120L128,232L96,120Z" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="16"/><line x1="72" y1="120" x2="184" y2="120" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="16"/><line x1="128" y1="120" x2="128" y2="176" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="16"/>
    </>
  ),
  Support: (
    <>
      <path d="M128,216S32,160,32,96A48,48,0,0,1,128,72a48,48,0,0,1,96,24C224,160,128,216,128,216Z" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="16"/><line x1="128" y1="104" x2="128" y2="160" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="16"/><line x1="100" y1="132" x2="156" y2="132" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="16"/>
    </>
  )
};

export function TraitIcon({ trait, className = "h-3.5 w-3.5" }: { trait: Trait; className?: string }) {
  return (
    <svg viewBox="0 0 256 256" className={`inline-block shrink-0 ${className}`} aria-hidden fill="none">
      {PATHS[trait]}
    </svg>
  );
}

/** A trait icon inside a dark hexagon with a thin light rim, TFT-style. */
export function TraitBadge({
  trait,
  className = "h-6 w-6",
  iconClass = "h-3.5 w-3.5",
  rimClass = "bg-white/30",
}: {
  trait: Trait;
  className?: string;
  iconClass?: string;
  /** Background of the outer hexagon, i.e. the rim colour (and the icon colour via text-*). */
  rimClass?: string;
}) {
  return (
    <span className={`hex relative inline-flex shrink-0 items-center justify-center ${rimClass} ${className}`}>
      <span className="hex absolute inset-[2px] bg-slate-900/95" aria-hidden />
      <TraitIcon trait={trait} className={`relative ${iconClass}`} />
    </span>
  );
}
