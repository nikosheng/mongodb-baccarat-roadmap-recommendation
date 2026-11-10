// Fly-across celebration animation triggered when "長莊連龍" becomes the
// top match. Pure CSS keyframes (see index.css: dragon-fly / dragon-bob /
// banner-fade) - no animation library dependency, consistent with the rest
// of the codebase. Mounted/unmounted by the caller via useLongDragonTrigger;
// this component has no internal timers of its own.

// Body segments ordered tail -> head. Because the whole row is translated
// to the right, the right-most DOM element (the head) leads the movement.
const BODY_SEGMENTS = ["莊", "莊", "莊", "莊", "莊", "莊", "莊"];

export function LongDragonAnimation() {
  return (
    <div className="fixed inset-x-0 top-[30%] z-[100] pointer-events-none overflow-hidden">
      <div
        className="flex items-center gap-2 whitespace-nowrap"
        style={{ animation: "dragon-fly 5s linear forwards" }}
      >
        {BODY_SEGMENTS.map((ch, i) => {
          const t = i / BODY_SEGMENTS.length; // 0 (tail) -> ~1 (near head)
          const fontSize = 24 + t * 28; // px, grows toward the head
          const opacity = 0.35 + t * 0.65;
          return (
            <span
              key={i}
              className="inline-block font-bold"
              style={{
                fontSize: `${fontSize}px`,
                opacity,
                color: "var(--color-banker)",
                textShadow: "0 0 8px rgba(220, 38, 38, 0.6)",
                animation: "dragon-bob 0.6s ease-in-out infinite",
                animationDelay: `${i * 80}ms`,
              }}
            >
              {ch}
            </span>
          );
        })}
        <span
          className="inline-block font-bold"
          style={{
            fontSize: "60px",
            color: "var(--color-accent-gold)",
            textShadow: "0 0 20px rgba(245, 158, 11, 0.9), 0 0 40px rgba(245, 158, 11, 0.5)",
            animation: "dragon-bob 0.6s ease-in-out infinite",
            animationDelay: `${BODY_SEGMENTS.length * 80}ms`,
          }}
        >
          龍
        </span>
      </div>

      <div
        className="mt-6 text-center text-2xl font-bold text-accent-gold"
        style={{
          textShadow: "0 0 12px rgba(245, 158, 11, 0.7)",
          animation: "banner-fade 5s linear forwards",
        }}
      >
        長莊連龍 🔥
      </div>
    </div>
  );
}
