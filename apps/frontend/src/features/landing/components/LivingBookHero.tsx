import { useEffect, useMemo, useRef, useState } from 'react';
import { LivingBookHeroProps } from './LivingBookHero.types';

export function LivingBookHero({
  baseImageUrl = '/images/book-base.png',
  mistRenderMode: initialMistRenderMode = 'blobs',
  blobCount = 5,
  dustCount = 20,
  mistOpacity = 0.15,
  mistBlur = 40,
  parallaxIntensity = 1,
  children,
}: LivingBookHeroProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mouseX = useRef(0);
  const mouseY = useRef(0);
  const targetX = useRef(0);
  const targetY = useRef(0);

  // Dev toggle state for the mist render mode
  const [mistRenderMode, setMistRenderMode] = useState(initialMistRenderMode);

  // Generate random stable properties for mist blobs
  const mistBlobs = useMemo(
    () =>
      Array.from({ length: blobCount }).map((_, i) => ({
        id: i,
        width: `${40 + Math.random() * 40}%`,
        height: `${40 + Math.random() * 40}%`,
        // Restrict to right 66% roughly, keeping the left third clear
        left: `${33 + Math.random() * 40}%`,
        top: `${20 + Math.random() * 40}%`,
        duration: 10 + Math.random() * 8, // 10-18s
        delay: -(Math.random() * 10), // Negative delay so it starts mid-animation
      })),
    [blobCount]
  );

  // Generate random stable properties for dust motes
  const dustMotes = useMemo(
    () =>
      Array.from({ length: dustCount }).map((_, i) => ({
        id: i,
        size: `${1 + Math.random() * 2}px`,
        // Restrict to right 67%
        left: `${33 + Math.random() * 66}%`,
        top: `${10 + Math.random() * 80}%`,
        duration: 6 + Math.random() * 8, // 6-14s
        delay: -(Math.random() * 8), // Negative delay
      })),
    [dustCount]
  );

  useEffect(() => {
    // Respect prefers-reduced-motion
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    if (mediaQuery.matches) return;
    
    // Disable on touch devices (where hover is usually simulated)
    const isTouch = window.matchMedia('(pointer: coarse)').matches;
    if (isTouch) return;

    const container = containerRef.current;
    if (!container) return;

    const handleMouseMove = (e: MouseEvent) => {
      const rect = container.getBoundingClientRect();
      const x = (e.clientX - rect.left) / rect.width - 0.5;
      const y = (e.clientY - rect.top) / rect.height - 0.5;
      targetX.current = x * 2; // Range -1 to 1
      targetY.current = y * 2; // Range -1 to 1
    };

    container.addEventListener('mousemove', handleMouseMove);

    let animationFrameId: number;
    const lerp = (start: number, end: number, amt: number) =>
      (1 - amt) * start + amt * end;

    const update = () => {
      mouseX.current = lerp(mouseX.current, targetX.current, 0.05);
      mouseY.current = lerp(mouseY.current, targetY.current, 0.05);

      if (containerRef.current) {
        containerRef.current.style.setProperty(
          '--mouse-x',
          mouseX.current.toString()
        );
        containerRef.current.style.setProperty(
          '--mouse-y',
          mouseY.current.toString()
        );
      }
      animationFrameId = requestAnimationFrame(update);
    };

    animationFrameId = requestAnimationFrame(update);

    return () => {
      container.removeEventListener('mousemove', handleMouseMove);
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  return (
    <div
      ref={containerRef}
      className="relative w-full min-h-screen overflow-hidden bg-black flex items-end justify-end"
      style={
        {
          '--parallax': parallaxIntensity,
          '--mouse-x': 0,
          '--mouse-y': 0,
        } as React.CSSProperties
      }
    >
      <style>{`
        @keyframes mist-drift {
          0% { transform: translateY(10%) translateX(0); opacity: 0; }
          25% { opacity: var(--max-opacity, 0.15); }
          75% { opacity: var(--max-opacity, 0.15); }
          100% { transform: translateY(-20%) translateX(5%); opacity: 0; }
        }
        @keyframes dust-drift {
          0% { transform: translateY(0) translateX(0); opacity: 0; }
          25% { opacity: 1; }
          75% { opacity: 1; }
          100% { transform: translateY(-80px) translateX(20px); opacity: 0; }
        }
        @keyframes glow-breathe {
          0%, 100% { opacity: 0.6; }
          50% { opacity: 1; }
        }
        
        .layer-parallax-glow {
          transform: translate(calc(var(--mouse-x) * 12px * var(--parallax)), calc(var(--mouse-y) * 12px * var(--parallax)));
          will-change: transform;
        }
        .layer-parallax-mist {
          transform: translate(calc(var(--mouse-x) * 6px * var(--parallax)), calc(var(--mouse-y) * 6px * var(--parallax)));
          will-change: transform;
        }
        .layer-parallax-dust {
          transform: translate(calc(var(--mouse-x) * 16px * var(--parallax)), calc(var(--mouse-y) * 16px * var(--parallax)));
          will-change: transform;
        }

        /* Reduced motion overrides */
        @media (prefers-reduced-motion: reduce) {
          .animate-mist, .animate-dust, .animate-glow, 
          .layer-parallax-glow, .layer-parallax-mist, .layer-parallax-dust {
            animation: none !important;
            transform: none !important;
          }
          .animate-glow { opacity: 0.8 !important; }
        }
      `}</style>

      {/* Layer 1: Static Base Image */}
      <img
        src={baseImageUrl}
        alt=""
        className="absolute inset-0 w-full h-full object-cover select-none pointer-events-none"
      />

      {/* Layer 2: Breathing Glow */}
      <div className="absolute inset-0 layer-parallax-glow pointer-events-none mix-blend-screen mix-blend-lighten">
        <div 
          className="absolute right-0 bottom-0 w-2/3 h-full animate-glow"
          style={{
            background: 'radial-gradient(circle at 60% 70%, rgba(255, 220, 150, 0.4), transparent 60%)',
            filter: `blur(${mistBlur}px)`,
            animation: 'glow-breathe 5s ease-in-out infinite',
            willChange: 'opacity'
          }}
        />
      </div>

      {/* Layer 3: Mist */}
      {mistRenderMode === 'blobs' ? (
        <div className="absolute inset-0 layer-parallax-mist pointer-events-none mix-blend-screen">
          {mistBlobs.map((blob) => (
            <div
              key={blob.id}
              className="absolute animate-mist rounded-full bg-[radial-gradient(circle,rgba(255,245,215,1),transparent_70%)]"
              style={{
                width: blob.width,
                height: blob.height,
                left: blob.left,
                top: blob.top,
                filter: `blur(${mistBlur}px)`,
                '--max-opacity': mistOpacity,
                opacity: 0, // Starts at 0, driven by keyframes
                animation: `mist-drift ${blob.duration}s ease-in-out infinite`,
                animationDelay: `${blob.delay}s`,
                willChange: 'transform, opacity'
              } as React.CSSProperties}
            />
          ))}
        </div>
      ) : (
        <div 
          className="absolute inset-0 layer-parallax-mist pointer-events-none mix-blend-screen opacity-70"
          style={{
            maskImage: 'linear-gradient(to right, transparent 0%, transparent 15%, black 45%, black 100%)',
            WebkitMaskImage: 'linear-gradient(to right, transparent 0%, transparent 15%, black 45%, black 100%)',
          }}
        >
          <svg className="w-full h-full">
            <filter id="mist-turbulence">
              <feTurbulence
                type="fractalNoise"
                baseFrequency="0.015 0.02"
                numOctaves="3"
                seed="5"
              >
                <animate
                  attributeName="baseFrequency"
                  values="0.015 0.02; 0.01 0.015; 0.015 0.02"
                  dur="15s"
                  repeatCount="indefinite"
                />
              </feTurbulence>
              <feColorMatrix
                type="matrix"
                values="
                  1 0 0 0 1
                  0 1 0 0 0.9
                  0 0 1 0 0.7
                  0 0 0 1 0
                "
              />
              <feComponentTransfer>
                <feFuncA type="linear" slope={mistOpacity} />
              </feComponentTransfer>
            </filter>
            {/* Render rect full width and rely on gradient mask for organic fade */}
            <rect
              x="0"
              y="0"
              width="100%"
              height="100%"
              filter="url(#mist-turbulence)"
              fill="transparent"
            />
          </svg>
        </div>
      )}

      {/* Layer 4: Dust Motes */}
      <div className="absolute inset-0 layer-parallax-dust pointer-events-none mix-blend-screen">
        {dustMotes.map((mote) => (
          <div
            key={mote.id}
            className="absolute rounded-full animate-dust bg-white"
            style={{
              width: mote.size,
              height: mote.size,
              left: mote.left,
              top: mote.top,
              boxShadow: '0 0 4px 1px rgba(255,220,150,0.6)',
              opacity: 0,
              animation: `dust-drift ${mote.duration}s linear infinite`,
              animationDelay: `${mote.delay}s`,
              willChange: 'transform, opacity'
            }}
          />
        ))}
      </div>

      {/* Children Content */}
      <div className="absolute inset-0 z-10 pointer-events-none">
        {children}
      </div>

      {/* Dev Toggle Button */}
      <div className="absolute top-4 right-4 z-50 pointer-events-auto">
        <button
          onClick={() => setMistRenderMode(prev => prev === 'blobs' ? 'svg-turbulence' : 'blobs')}
          className="px-3 py-1 text-xs font-mono bg-black/60 text-white/80 border border-white/20 rounded hover:bg-black/80 hover:text-white transition-colors backdrop-blur-md cursor-pointer pointer-events-auto"
        >
          Dev: Mist Mode = {mistRenderMode}
        </button>
      </div>
    </div>
  );
}
