import { useEffect, useRef, useCallback, useMemo } from 'react';
import createGlobe from 'cobe';
import type { APIRegion } from '../api/client';

// Geographic coordinates for each region
const REGION_COORDS: Record<string, [number, number]> = {
  'usa':            [38.9,  -77.0],   // Washington DC
  'europe':         [50.1,   8.7],    // Frankfurt
  'japan':          [35.7,  139.7],    // Tokyo
  'china':          [39.9,  116.4],    // Beijing
  'emerging':       [19.4,   72.9],   // Mumbai
  'nordics':        [59.3,   18.1],    // Stockholm
  'uk':             [51.5,   -0.1],    // London
  'latin-america':  [-23.5,  -46.6],  // São Paulo
  // fallbacks
  'asia':           [35.7,  139.7],
  'pacific':        [-33.9,  151.2],
  'middle-east':    [25.3,   55.3],
  'africa':         [-1.3,   36.8],
};

interface MarketGlobeProps {
  regions: APIRegion[];
}

export default function MarketGlobe({ regions }: MarketGlobeProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const pointerInteracting = useRef<{ x: number; y: number } | null>(null);
  const dragOffset = useRef({ phi: 0, theta: 0 });
  const phiOffsetRef = useRef(0);
  const thetaOffsetRef = useRef(0);
  const isPausedRef = useRef(false);

  // Map regions to globe markers
  const markers = useMemo(() =>
    regions.map(r => {
      const coords = REGION_COORDS[r.id] || [0, 0];
      return {
        location: coords as [number, number],
        size: Math.max(0.04, Math.min(0.12, Math.abs(r.score) * 0.012)),
      };
    }),
    [regions]
  );

  // Map regions to labels with screen positions (computed during render)
  const labelPositions = useMemo(() =>
    regions.map(r => {
      const coords = REGION_COORDS[r.id];
      return {
        region: r,
        lat: coords ? coords[0] : 0,
        lng: coords ? coords[1] : 0,
      };
    }),
    [regions]
  );

  const handlePointerDown = useCallback((e: React.PointerEvent) => {
    pointerInteracting.current = { x: e.clientX, y: e.clientY };
    if (canvasRef.current) canvasRef.current.style.cursor = 'grabbing';
    isPausedRef.current = true;
  }, []);

  const handlePointerUp = useCallback(() => {
    if (pointerInteracting.current !== null) {
      phiOffsetRef.current += dragOffset.current.phi;
      thetaOffsetRef.current += dragOffset.current.theta;
      dragOffset.current = { phi: 0, theta: 0 };
    }
    pointerInteracting.current = null;
    if (canvasRef.current) canvasRef.current.style.cursor = 'grab';
    isPausedRef.current = false;
  }, []);

  useEffect(() => {
    const handlePointerMove = (e: PointerEvent) => {
      if (pointerInteracting.current !== null) {
        dragOffset.current = {
          phi: (e.clientX - pointerInteracting.current.x) / 200,
          theta: (e.clientY - pointerInteracting.current.y) / 600,
        };
      }
    };
    window.addEventListener('pointermove', handlePointerMove, { passive: true });
    window.addEventListener('pointerup', handlePointerUp, { passive: true });
    return () => {
      window.removeEventListener('pointermove', handlePointerMove);
      window.removeEventListener('pointerup', handlePointerUp);
    };
  }, [handlePointerUp]);

  useEffect(() => {
    if (!canvasRef.current) return;
    const canvas = canvasRef.current;
    let globe: ReturnType<typeof createGlobe> | null = null;
    let animationId: number;
    let phi = 0;

    function init() {
      const width = canvas.offsetWidth;
      if (width === 0 || globe) return;

      globe = createGlobe(canvas, {
        devicePixelRatio: Math.min(window.devicePixelRatio || 1, 2),
        width: width * 2,
        height: width * 2,
        phi: 0,
        theta: 0.15,
        dark: 1,
        diffuse: 1.5,
        mapSamples: 20000,
        mapBrightness: 8,
        baseColor: [0.15, 0.18, 0.25],
        markerColor: [0.2, 0.85, 0.95],
        glowColor: [0.03, 0.06, 0.1],
        markers: markers,
      });

      function animate() {
        if (!isPausedRef.current) phi += 0.002;
        globe!.update({
          phi: phi + phiOffsetRef.current + dragOffset.current.phi,
          theta: 0.15 + thetaOffsetRef.current + dragOffset.current.theta,
        });
        animationId = requestAnimationFrame(animate);
      }
      animate();
      setTimeout(() => {
        if (canvas) canvas.style.opacity = '1';
      }, 100);
    }

    if (canvas.offsetWidth > 0) {
      init();
    } else {
      const ro = new ResizeObserver((entries) => {
        if (entries[0]?.contentRect.width > 0) {
          ro.disconnect();
          init();
        }
      });
      ro.observe(canvas);
    }

    return () => {
      if (animationId) cancelAnimationFrame(animationId);
      if (globe) globe.destroy();
    };
  }, [markers]);

  // Score color helper
  const getScoreStyle = (score: number) => {
    if (score >= 4) return { color: '#00ff88', bg: 'rgba(0,255,136,0.15)', border: '1px solid rgba(0,255,136,0.3)' };
    if (score >= 1) return { color: '#4facfe', bg: 'rgba(79,172,254,0.15)', border: '1px solid rgba(79,172,254,0.3)' };
    if (score >= -1) return { color: '#888', bg: 'rgba(136,136,136,0.12)', border: '1px solid rgba(136,136,136,0.2)' };
    if (score >= -4) return { color: '#ff8844', bg: 'rgba(255,136,68,0.15)', border: '1px solid rgba(255,136,68,0.3)' };
    return { color: '#ff4466', bg: 'rgba(255,68,102,0.15)', border: '1px solid rgba(255,68,102,0.3)' };
  };

  return (
    <div
      ref={containerRef}
      className="glass-panel"
      style={{
        padding: '1.5rem',
        marginBottom: '2rem',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      <h3 style={{
        marginBottom: '1rem',
        fontSize: '1.1rem',
        display: 'flex',
        alignItems: 'center',
        gap: '0.5rem',
        color: 'var(--text-primary)',
      }}>
        🌍 Global Markets
      </h3>

      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: '1.5rem',
        alignItems: 'center',
      }}>
        {/* Globe */}
        <div style={{
          position: 'relative',
          aspectRatio: '1',
          maxWidth: '400px',
          margin: '0 auto',
          width: '100%',
        }}>
          <canvas
            ref={canvasRef}
            onPointerDown={handlePointerDown}
            style={{
              width: '100%',
              height: '100%',
              cursor: 'grab',
              opacity: 0,
              transition: 'opacity 1.2s ease',
              touchAction: 'none',
            }}
          />

          {/* Pulse animations */}
          <style>{`
            @keyframes globe-pulse {
              0% { transform: scale(0.5); opacity: 0.6; }
              100% { transform: scale(2.5); opacity: 0; }
            }
            @keyframes globe-glow {
              0%, 100% { box-shadow: 0 0 20px rgba(79,172,254,0.2); }
              50% { box-shadow: 0 0 40px rgba(79,172,254,0.4); }
            }
          `}</style>

          {/* Subtle ambient glow behind globe */}
          <div style={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            width: '80%',
            height: '80%',
            borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(79,172,254,0.08) 0%, transparent 70%)',
            pointerEvents: 'none',
            zIndex: -1,
          }} />
        </div>

        {/* Market Labels */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '0.5rem',
        }}>
          {labelPositions.map(({ region }, i) => {
            const style = getScoreStyle(region.score);
            return (
              <div
                key={region.id}
                className="animate-fade-in"
                style={{
                  padding: '0.6rem 0.75rem',
                  borderRadius: '10px',
                  background: style.bg,
                  border: style.border,
                  animationDelay: `${i * 0.08}s`,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  transition: 'transform 0.2s ease',
                  cursor: 'default',
                }}
                onMouseEnter={e => (e.currentTarget.style.transform = 'scale(1.03)')}
                onMouseLeave={e => (e.currentTarget.style.transform = 'scale(1)')}
              >
                <span style={{ fontSize: '1.2rem' }}>{region.flag}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    color: 'var(--text-primary)',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}>
                    {region.name}
                  </div>
                  <div style={{
                    fontSize: '0.65rem',
                    color: 'var(--text-tertiary)',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}>
                    {region.indexName}
                  </div>
                </div>
                <div style={{
                  fontSize: '1rem',
                  fontWeight: 700,
                  color: style.color,
                  fontFamily: 'monospace',
                  minWidth: '2.5rem',
                  textAlign: 'right',
                }}>
                  {region.score > 0 ? '+' : ''}{region.score}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
