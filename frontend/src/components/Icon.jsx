// Line icons (stroke = currentColor) used across the app shell and pages.
const PATHS = {
  today: <><rect x="3" y="3" width="7" height="9" rx="1" /><rect x="14" y="3" width="7" height="5" rx="1" /><rect x="14" y="12" width="7" height="9" rx="1" /><rect x="3" y="16" width="7" height="5" rx="1" /></>,
  farms: <><path d="M3 21V10l9-6 9 6v11" /><path d="M9 21v-6h6v6" /></>,
  flocks: <ellipse cx="12" cy="13" rx="6" ry="8" />,
  feed: <><path d="M6 3h12l-1 4H7z" /><path d="M7 7l-1 14h12L17 7" /></>,
  reports: <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />,
  insights: <><path d="M9 18h6M10 21h4" /><path d="M12 3a6 6 0 00-3.5 10.9V16h7v-2.1A6 6 0 0012 3z" /></>,
  users: <><circle cx="9" cy="8" r="3.5" /><path d="M2.5 20a6.5 6.5 0 0113 0" /><path d="M16 4.5a3.5 3.5 0 010 7M18 14a6 6 0 013.5 6" /></>,
  settings: <><circle cx="12" cy="12" r="3" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1" /></>,
  trash: <path d="M4 7h16M10 11v6M14 11v6M5 7l1 13h12l1-13M9 7V4h6v3" />,
  switch: <path d="M7 4L3 8l4 4M3 8h14M17 20l4-4-4-4M21 16H7" />,
  search: <><circle cx="11" cy="11" r="7" /><path d="M20 20l-3.5-3.5" /></>,
  bell: <path d="M6 8a6 6 0 0112 0c0 7 3 9 3 9H3s3-2 3-9M10.3 21a1.9 1.9 0 003.4 0" />,
  menu: <path d="M4 6h16M4 12h16M4 18h16" />,
  close: <path d="M6 6l12 12M18 6L6 18" />,
  plus: <path d="M12 5v14M5 12h14" />,
  entry: <><path d="M9 4h6v3H9z" /><path d="M7 5H5v16h14V5h-2M9 12h6M9 16h4" /></>,
  sale: <><path d="M3 7h18v10H3z" /><circle cx="12" cy="12" r="2.5" /></>,
  ledger: <><path d="M5 3h12a2 2 0 012 2v16H7a2 2 0 01-2-2z" /><path d="M9 7h6M9 11h6" /></>,
  egg: <path d="M12 3c-3.5 0-6 6-6 10a6 6 0 0012 0c0-4-2.5-10-6-10z" />,
  logout: <path d="M15 4h4v16h-4M10 8l-4 4 4 4M6 12h10" />,
  key: <><circle cx="8" cy="15" r="4" /><path d="M11 12l9-9M17 6l3 3" /></>,
  heat: <path d="M14 14.8V4a2 2 0 10-4 0v10.8a4 4 0 104 0z" />,
};

export default function Icon({ name, size = 18, className, title }) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"
         aria-hidden={title ? undefined : 'true'} role={title ? 'img' : undefined} aria-label={title}>
      {PATHS[name] || null}
    </svg>
  );
}
