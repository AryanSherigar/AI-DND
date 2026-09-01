import { useMemo } from "react";

interface BackgroundMistProps {
  opacity?: number;
  blobCount?: number;
}

export function BackgroundMist({
  opacity = 0.55,
  blobCount = 8,
}: BackgroundMistProps) {
  const mistBlobs = useMemo(
    () =>
      Array.from({ length: blobCount }).map((_, i) => ({
        id: i,
        width: `${45 + Math.random() * 45}%`,
        height: `${45 + Math.random() * 45}%`,
        left: `${-15 + Math.random() * 90}%`,
        top: `${-15 + Math.random() * 90}%`,
        duration: 12 + Math.random() * 10,
        delay: -(Math.random() * 10),
      })),
    [blobCount],
  );

  const dustParticles = useMemo(
    () =>
      Array.from({ length: 30 }).map((_, i) => ({
        id: i,
        size: Math.random() * 3.5 + 1.5,
        left: `${Math.random() * 100}%`,
        top: `${Math.random() * 100}%`,
        duration: 5 + Math.random() * 7,
        delay: -(Math.random() * 7),
      })),
    [],
  );

  return (
    <div className="fixed inset-0 pointer-events-none overflow-hidden z-0">
      <style>{`
        @keyframes play-mist-drift {
          0% { transform: translateY(10%) translateX(-8%) scale(1); opacity: 0; }
          35% { opacity: var(--max-opacity, 0.55); }
          65% { opacity: var(--max-opacity, 0.55); }
          100% { transform: translateY(-18%) translateX(14%) scale(1.2); opacity: 0; }
        }
        @keyframes play-dust-float {
          0% { transform: translateY(0px) translateX(0px); opacity: 0.2; }
          50% { opacity: 0.9; }
          100% { transform: translateY(-40px) translateX(20px); opacity: 0.2; }
        }
      `}</style>

      {/* Dark Ambient Base Gradient */}
      <div className="absolute inset-0 bg-gradient-to-b from-stone-950 via-zinc-950 to-neutral-950" />

      {/* SVG Animated Fractal Noise Mist Layer */}
      <div className="absolute inset-0 opacity-40 mix-blend-screen">
        <svg className="w-full h-full">
          <filter id="play-mist-turbulence">
            <feTurbulence
              type="fractalNoise"
              baseFrequency="0.012 0.018"
              numOctaves="3"
              seed="12"
            >
              <animate
                attributeName="baseFrequency"
                values="0.012 0.018; 0.008 0.012; 0.012 0.018"
                dur="20s"
                repeatCount="indefinite"
              />
            </feTurbulence>
            <feColorMatrix
              type="matrix"
              values="
                1 0 0 0 0.95
                0 0.7 0 0 0.55
                0 0 0.3 0 0.2
                0 0 0 0.6 0
              "
            />
            <feComponentTransfer>
              <feFuncA type="linear" slope={opacity * 0.8} />
            </feComponentTransfer>
          </filter>
          <rect
            width="100%"
            height="100%"
            filter="url(#play-mist-turbulence)"
            fill="transparent"
          />
        </svg>
      </div>

      {/* Glowing Amber Light Blobs */}
      {mistBlobs.map((blob) => (
        <div
          key={blob.id}
          className="absolute rounded-full mix-blend-screen bg-[radial-gradient(circle,rgba(251,191,36,0.45)_0%,rgba(217,119,6,0.22)_45%,transparent_70%)]"
          style={{
            width: blob.width,
            height: blob.height,
            left: blob.left,
            top: blob.top,
            filter: "blur(60px)",
            opacity: 0,
            animation: `play-mist-drift ${blob.duration}s ease-in-out infinite`,
            animationDelay: `${blob.delay}s`,
            ["--max-opacity" as string]: opacity,
          }}
        />
      ))}

      {/* Floating Ember Dust Particles */}
      {dustParticles.map((particle) => (
        <div
          key={particle.id}
          className="absolute rounded-full bg-amber-400/80 shadow-[0_0_10px_rgba(251,191,36,0.9)]"
          style={{
            width: `${particle.size}px`,
            height: `${particle.size}px`,
            left: particle.left,
            top: particle.top,
            animation: `play-dust-float ${particle.duration}s ease-in-out infinite alternate`,
            animationDelay: `${particle.delay}s`,
          }}
        />
      ))}
    </div>
  );
}
