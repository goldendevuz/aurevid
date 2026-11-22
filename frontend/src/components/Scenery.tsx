// SPDX-License-Identifier: AGPL-3.0-or-later
// Ambient dark studio subtle backdrop for landing hero.

export default function Scenery() {
  return (
    <div className="pointer-events-none absolute inset-0 -z-10 overflow-hidden" aria-hidden>
      <div className="absolute -top-40 left-1/2 h-[500px] w-[800px] -translate-x-1/2 rounded-full bg-accent/[0.04] blur-[120px]" />
    </div>
  );
}
