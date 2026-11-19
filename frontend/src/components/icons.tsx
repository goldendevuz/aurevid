// SPDX-License-Identifier: AGPL-3.0-or-later
// Small original stroke icon set (24px grid, 1.75 stroke). Decorative by default: pass `title`
// only when the icon is the sole content of a control that has no text/aria-label of its own.
import type { SVGProps } from "react";

const PATHS = {
  image: "M4 6.5A2.5 2.5 0 0 1 6.5 4h11A2.5 2.5 0 0 1 20 6.5v11a2.5 2.5 0 0 1-2.5 2.5h-11A2.5 2.5 0 0 1 4 17.5v-11Zm0 9 4.2-4.2a1.5 1.5 0 0 1 2.1 0L15 16m-1.5-1.5 1.2-1.2a1.5 1.5 0 0 1 2.1 0L20 16M15.5 9.2h.01",
  video: "M4 7.5A2.5 2.5 0 0 1 6.5 5h6A2.5 2.5 0 0 1 15 7.5v9a2.5 2.5 0 0 1-2.5 2.5h-6A2.5 2.5 0 0 1 4 16.5v-9ZM15 10.5l4.2-2.4a.8.8 0 0 1 1.2.7v6.4a.8.8 0 0 1-1.2.7L15 13.5",
  sparkle: "M12 3.5 13.9 9l5.6 1.9-5.6 1.9L12 18.5l-1.9-5.7L4.5 10.9 10.1 9 12 3.5ZM18.5 16l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7.7-2Z",
  star: "m12 4 2.4 5 5.4.7-4 3.7 1 5.4L12 16.1 7.2 18.8l1-5.4-4-3.7 5.4-.7L12 4Z",
  download: "M12 4v11m0 0-4-4m4 4 4-4M5 19.5h14",
  expand: "M14 4h6v6m0-6-7 7M10 20H4v-6m0 6 7-7",
  play: "M8 5.6v12.8a.8.8 0 0 0 1.2.7l10-6.4a.8.8 0 0 0 0-1.4l-10-6.4A.8.8 0 0 0 8 5.6Z",
  flag: "M5 21V4m0 0h11l-1.8 4L16 12H5",
  trash: "M5 7h14M10 7V4.5h4V7m-7 0 .8 12a1.5 1.5 0 0 0 1.5 1.4h5.4a1.5 1.5 0 0 0 1.5-1.4L17 7M10 11v6m4-6v6",
  copy: "M8 8V6.5A2.5 2.5 0 0 1 10.5 4h7A2.5 2.5 0 0 1 20 6.5v7a2.5 2.5 0 0 1-2.5 2.5H16M6.5 8h7A2.5 2.5 0 0 1 16 10.5v7a2.5 2.5 0 0 1-2.5 2.5h-7A2.5 2.5 0 0 1 4 17.5v-7A2.5 2.5 0 0 1 6.5 8Z",
  chevron: "m7 10 5 5 5-5",
  close: "M6 6l12 12M18 6 6 18",
  check: "m5 12.5 4.5 4.5L19 7.5",
  key: "M14.5 9.5a4 4 0 1 1-1.2-2.9M13.3 6.6 20 13.5m-3 -3 2 2m-5 1 2 2",
  lock: "M7 11V8.5a5 5 0 0 1 10 0V11M6.5 11h11a1.5 1.5 0 0 1 1.5 1.5v6a1.5 1.5 0 0 1-1.5 1.5h-11A1.5 1.5 0 0 1 5 18.5v-6A1.5 1.5 0 0 1 6.5 11Z",
  ratio: "M4 8.5A1.5 1.5 0 0 1 5.5 7h13A1.5 1.5 0 0 1 20 8.5v7a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 15.5v-7Z",
  layers: "m12 4 8 4.5-8 4.5-8-4.5L12 4Zm-8 8 8 4.5 8-4.5M4 15.5 12 20l8-4.5",
  clock: "M12 7.5V12l3 2M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z",
  camera: "M4 8.5A2.5 2.5 0 0 1 6.5 6h1.2l1-1.6A1 1 0 0 1 9.6 4h4.8a1 1 0 0 1 .9.4l1 1.6h1.2A2.5 2.5 0 0 1 20 8.5v8A2.5 2.5 0 0 1 17.5 19h-11A2.5 2.5 0 0 1 4 16.5v-8ZM15.5 12.5a3.5 3.5 0 1 1-7 0 3.5 3.5 0 0 1 7 0Z",
  wand: "m5 19 9.5-9.5m0 0 2 2m-2-2 1.2-1.2a1.5 1.5 0 0 1 2.1 0l.1.1a1.5 1.5 0 0 1 0 2.1L16.5 11.6M6 5l.6 1.4L8 7l-1.4.6L6 9l-.6-1.4L4 7l1.4-.6L6 5Z",
  history: "M4 12a8 8 0 1 0 2.5-5.8M4 5v4h4M12 8v4l2.5 1.5",
  coins: "M12 6c-4 0-7 1-7 2.5S8 11 12 11s7-1 7-2.5S16 6 12 6ZM5 8.5v4C5 14 8 15 12 15s7-1 7-2.5v-4M5 12.5v4C5 18 8 19 12 19s7-1 7-2.5v-4",
  settings: "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm7.4-2.5.1-1-.1-1 1.9-1.5-1.8-3.1-2.3.8a7 7 0 0 0-1.7-1L15 3.5h-3.6l-.5 2.2a7 7 0 0 0-1.7 1l-2.3-.8-1.8 3.1L7 10.5l-.1 1 .1 1-1.9 1.5 1.8 3.1 2.3-.8c.5.4 1.1.7 1.7 1l.5 2.2H15l.5-2.2c.6-.3 1.2-.6 1.7-1l2.3.8 1.8-3.1-1.9-1.5Z",
  shield: "M12 3.5 5 6v5.5c0 4.2 2.9 7.3 7 9 4.1-1.7 7-4.8 7-9V6l-7-2.5Z",
  megaphone: "M4 10.5v3a1 1 0 0 0 1 1h2l5 4V5.5l-5 4H5a1 1 0 0 0-1 1ZM16 9.5a4 4 0 0 1 0 5M18.5 7a7.5 7.5 0 0 1 0 10",
  logout: "M10 5H6.5A1.5 1.5 0 0 0 5 6.5v11A1.5 1.5 0 0 0 6.5 19H10M15 8l4 4-4 4M19 12H9",
  search: "m20 20-3.8-3.8M10.5 17a6.5 6.5 0 1 1 0-13 6.5 6.5 0 0 1 0 13Z",
  arrow: "M5 12h14m0 0-5-5m5 5-5 5",
  sound: "M4 10v4a1 1 0 0 0 1 1h2.5l4.5 3.5v-13L7.5 9H5a1 1 0 0 0-1 1ZM16 9.5a3.5 3.5 0 0 1 0 5M18.5 7a7 7 0 0 1 0 10",
  bolt: "M13 3.5 5.5 13H11l-1 7.5L18.5 11H13l0-7.5Z",
  retry: "M19.5 12a7.5 7.5 0 1 1-2.2-5.3M19.5 4.5v4.5H15",
  filter: "M4 6h16M7 12h10M10 18h4",
} as const;

export type IconName = keyof typeof PATHS;

export function Icon({ name, size = 18, title, ...rest }: { name: IconName; size?: number; title?: string } & Omit<SVGProps<SVGSVGElement>, "name">) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      role={title ? "img" : undefined}
      aria-hidden={title ? undefined : true}
      aria-label={title}
      {...rest}
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
