// SPDX-License-Identifier: AGPL-3.0-or-later
// "Neon Coast" backdrop for the landing hero: a striped setting sun, a city skyline, two swaying palms and a
// scrolling perspective grid. Original SVG + CSS (see docs/design.md); purely decorative, so hidden from AT.

/** One palm: a curved trunk and a crown of fronds, drawn as a single dark silhouette. */
function Palm({ className, flip = false }: { className?: string; flip?: boolean }) {
  return (
    <svg
      viewBox="0 0 120 260"
      className={className}
      style={flip ? { transform: "scaleX(-1)" } : undefined}
      aria-hidden
    >
      <g className={flip ? "palm-sway-slow" : "palm-sway"} fill="#0b0414">
        <path d="M60 258c-4-60 2-120 14-176l6 2c-11 55-16 114-12 174z" />
        <path d="M76 80c-18-14-44-16-66-4 22-2 42 2 60 12z" />
        <path d="M76 80c-6-20-24-36-46-40 18 10 32 24 40 42z" />
        <path d="M78 80c6-22 24-36 44-38-16 10-30 24-38 42z" />
        <path d="M78 82c20-10 38-6 42 6-12-6-26-6-40 0z" />
        <path d="M77 82c-10 10-22 26-26 46 8-16 18-30 30-42z" />
        <path d="M79 82c12 8 22 22 24 42-8-14-16-26-28-36z" />
        <circle cx="77" cy="84" r="5" />
      </g>
    </svg>
  );
}

export default function Scenery() {
  // Gaps in the sun widen toward the horizon, the classic printed-poster sunset.
  const stripes = [
    { y: 112, h: 3 },
    { y: 128, h: 5 },
    { y: 144, h: 7 },
    { y: 160, h: 9 },
    { y: 176, h: 12 },
  ];
  return (
    <div className="pointer-events-none absolute inset-0 -z-10 overflow-hidden" aria-hidden>
      {/* Sun */}
      <svg viewBox="0 0 200 200" className="sun-glow absolute bottom-[34%] left-1/2 w-[min(78vw,560px)] -translate-x-1/2 opacity-90">
        <defs>
          <linearGradient id="nc-sun" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#ffe08a" />
            <stop offset="0.45" stopColor="#ff9a3c" />
            <stop offset="1" stopColor="#ff3e8a" />
          </linearGradient>
          <mask id="nc-sun-mask">
            <rect width="200" height="200" fill="#fff" />
            {stripes.map((s) => (
              <rect key={s.y} x="0" y={s.y} width="200" height={s.h} fill="#000" />
            ))}
          </mask>
        </defs>
        <circle cx="100" cy="100" r="96" fill="url(#nc-sun)" mask="url(#nc-sun-mask)" />
      </svg>

      {/* Skyline, sitting on the horizon */}
      <svg
        viewBox="0 0 1200 140"
        preserveAspectRatio="xMidYMax slice"
        className="absolute bottom-[30%] left-0 h-[14%] w-full"
      >
        <path
          fill="#1a0930"
          d="M0 140V96h40V70h22v26h30V54h18V40h12v14h16v42h28V80h34v60zM230 140V64h26V30h8v34h22v76zM300 140V88h36V58h40v82zM390 140V76h20V44h30v32h18v64zM470 140V92h44V20h6v-6h4v6h6v72h30v48zM578 140V70h32V52h28v88zM650 140V84h24V60h48v80zM736 140V40h14V26h20v14h14v100zM800 140V90h36V66h30v74zM880 140V58h26v-8h22v8h14v82zM956 140V80h40V62h22v78zM1030 140V92h26V48h34v92zM1104 140V74h30V56h22v18h44v66z"
        />
        {/* A few lit windows that flicker like neon */}
        <g className="neon-flicker" fill="#19e3d3" opacity="0.7">
          <rect x="246" y="76" width="4" height="4" />
          <rect x="486" y="40" width="4" height="4" />
          <rect x="752" y="56" width="4" height="4" />
          <rect x="896" y="72" width="4" height="4" />
        </g>
        <g fill="#ff3e8a" opacity="0.65">
          <rect x="320" y="70" width="4" height="4" />
          <rect x="590" y="84" width="4" height="4" />
          <rect x="1050" y="64" width="4" height="4" />
        </g>
      </svg>

      {/* Horizon line and the sea of neon grid below it */}
      <div className="absolute inset-x-0 bottom-0 h-[30%] bg-gradient-to-b from-[#2a0d3d] to-bg">
        <div className="absolute inset-x-0 top-0 h-px bg-accent/70 shadow-[0_0_18px_2px_rgb(255_62_138/0.6)]" />
        <div className="grid-floor" />
      </div>

      {/* Palms frame the scene on wide screens */}
      <Palm className="absolute bottom-[22%] left-[-2%] hidden h-[62%] md:block" />
      <Palm flip className="absolute bottom-[24%] right-[-1%] hidden h-[54%] md:block" />

      {/* Fade into the page below */}
      <div className="absolute inset-x-0 bottom-0 h-24 bg-gradient-to-b from-transparent to-bg" />
    </div>
  );
}
