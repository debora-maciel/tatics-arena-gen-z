/** Inline icons. They use currentColor so they follow the surrounding text colour. */

/** Stack of coins, from public/assets/icons/coin.svg. */
export function CoinIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg viewBox="0 0 256 256" className={className} aria-hidden fill="none">
      <ellipse cx="128" cy="104" rx="104" ry="48" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="16"/><line x1="128" y1="152" x2="128" y2="200" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="16"/><path d="M24,104v48c0,24,40,48,104,48s104-24,104-48V104" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="16"/><line x1="192" y1="142.11" x2="192" y2="190.11" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="16"/><line x1="64" y1="142.11" x2="64" y2="190.11" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="16"/>
    </svg>
  );
}
