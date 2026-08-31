/**
 * Inline stroke icons.
 *
 * Kept as local SVG components rather than an icon package so the bundle stays
 * small and every glyph inherits `currentColor` from the surrounding theme.
 */

const base = {
  width: 20,
  height: 20,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  'aria-hidden': 'true',
  focusable: 'false',
};

const icon = (path) =>
  function Icon(props) {
    return (
      <svg {...base} {...props}>
        {path}
      </svg>
    );
  };

export const IconHome = icon(
  <>
    <path d="M3 10.5 12 3l9 7.5" />
    <path d="M5 9.5V21h14V9.5" />
  </>,
);

export const IconMap = icon(
  <>
    <path d="m9 3-6 3v15l6-3 6 3 6-3V3l-6 3z" />
    <path d="M9 3v15M15 6v15" />
  </>,
);

export const IconPin = icon(
  <>
    <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0z" />
    <circle cx="12" cy="10" r="3" />
  </>,
);

export const IconNear = icon(
  <>
    <circle cx="12" cy="12" r="3" />
    <path d="M12 2v3M12 19v3M2 12h3M19 12h3" />
    <circle cx="12" cy="12" r="8" />
  </>,
);

export const IconReport = icon(
  <>
    <path d="M12 9v4M12 17h.01" />
    <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
  </>,
);

export const IconList = icon(
  <>
    <path d="M8 6h13M8 12h13M8 18h13" />
    <path d="M3 6h.01M3 12h.01M3 18h.01" />
  </>,
);

export const IconBell = icon(
  <>
    <path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
    <path d="M13.7 21a2 2 0 0 1-3.4 0" />
  </>,
);

export const IconUser = icon(
  <>
    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
    <circle cx="12" cy="7" r="4" />
  </>,
);

export const IconSearch = icon(
  <>
    <circle cx="11" cy="11" r="8" />
    <path d="m21 21-4.3-4.3" />
  </>,
);

export const IconRamp = icon(
  <>
    <path d="M3 19h18" />
    <path d="M4 19 18 6" />
    <path d="M18 6v13" />
  </>,
);

export const IconDoor = icon(
  <>
    <path d="M4 21V4a1 1 0 0 1 1-1h9a1 1 0 0 1 1 1v17" />
    <path d="M2 21h20" />
    <circle cx="12" cy="12" r="1" />
  </>,
);

export const IconToilet = icon(
  <>
    <circle cx="12" cy="5" r="2" />
    <path d="M12 8v6M9 21l1.5-5M15 21l-1.5-5" />
    <path d="M8 11h8" />
  </>,
);

export const IconParking = icon(
  <>
    <rect x="3" y="3" width="18" height="18" rx="3" />
    <path d="M9 17V7h3.5a3 3 0 0 1 0 6H9" />
  </>,
);

export const IconCrossing = icon(
  <>
    <path d="M4 20 8 4M10 20l4-16M16 20l4-16" />
  </>,
);

export const IconPath = icon(
  <>
    <path d="M4 20c4 0 4-8 8-8s4 8 8 8" />
    <circle cx="4" cy="20" r="1.5" />
    <circle cx="20" cy="20" r="1.5" />
  </>,
);

export const IconCamera = icon(
  <>
    <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
    <circle cx="12" cy="13" r="4" />
  </>,
);

export const IconImage = icon(
  <>
    <rect x="3" y="3" width="18" height="18" rx="2" />
    <circle cx="8.5" cy="8.5" r="1.5" />
    <path d="m21 15-5-5L5 21" />
  </>,
);

export const IconUpload = icon(
  <>
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
    <path d="m17 8-5-5-5 5M12 3v12" />
  </>,
);

export const IconCheck = icon(<path d="M20 6 9 17l-5-5" />);

export const IconX = icon(
  <>
    <path d="M18 6 6 18M6 6l12 12" />
  </>,
);

export const IconClock = icon(
  <>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3 2" />
  </>,
);

export const IconChevronLeft = icon(<path d="m15 18-6-6 6-6" />);
export const IconChevronRight = icon(<path d="m9 18 6-6-6-6" />);

export const IconDashboard = icon(
  <>
    <rect x="3" y="3" width="7" height="9" rx="1.5" />
    <rect x="14" y="3" width="7" height="5" rx="1.5" />
    <rect x="14" y="12" width="7" height="9" rx="1.5" />
    <rect x="3" y="16" width="7" height="5" rx="1.5" />
  </>,
);

export const IconWrench = icon(
  <path d="M14.7 6.3a4 4 0 0 0 5 5l-9.4 9.4a2.8 2.8 0 0 1-4-4z" />,
);

export const IconChart = icon(
  <>
    <path d="M3 3v18h18" />
    <path d="M7 15V9M12 17V5M17 17v-8" />
  </>,
);

export const IconShield = icon(
  <>
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    <path d="m9 12 2 2 4-4" />
  </>,
);

export const IconLogout = icon(
  <>
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
    <path d="m16 17 5-5-5-5M21 12H9" />
  </>,
);

export const IconMenu = icon(<path d="M3 6h18M3 12h18M3 18h18" />);

export const IconLocate = icon(
  <>
    <circle cx="12" cy="12" r="7" />
    <circle cx="12" cy="12" r="2" />
    <path d="M12 2v3M12 19v3M2 12h3M19 12h3" />
  </>,
);

export const IconInbox = icon(
  <>
    <path d="M22 12h-6l-2 3h-4l-2-3H2" />
    <path d="M5.5 5h13l3.5 7v7a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-7z" />
  </>,
);

export const IconSpark = icon(
  <>
    <path d="M12 3v4M12 17v4M3 12h4M17 12h4" />
    <path d="m6 6 2.5 2.5M15.5 15.5 18 18M18 6l-2.5 2.5M8.5 15.5 6 18" />
  </>,
);

export const IconFile = icon(
  <>
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
    <path d="M14 2v6h6" />
  </>,
);

export const IconLogo = (props) => (
  <svg viewBox="0 0 64 64" width={28} height={28} aria-hidden="true" {...props}>
    <path
      d="M14 46h10l14-24h10"
      stroke="currentColor"
      strokeWidth="6"
      strokeLinecap="round"
      strokeLinejoin="round"
      fill="none"
    />
    <circle cx="24" cy="20" r="6" fill="currentColor" opacity="0.65" />
    <circle cx="44" cy="46" r="6" fill="currentColor" opacity="0.65" />
  </svg>
);

/** Icon for an accessibility facility category. */
export function facilityIcon(type, props = {}) {
  const map = {
    Ramp: IconRamp,
    Entrance: IconDoor,
    Toilet: IconToilet,
    Parking: IconParking,
    Crossing: IconCrossing,
    Pathway: IconPath,
  };
  const Component = map[type] || IconPin;
  return <Component {...props} />;
}
