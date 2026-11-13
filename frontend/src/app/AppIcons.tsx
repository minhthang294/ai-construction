import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

function Icon({ children, ...props }: IconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...props}
    >
      {children}
    </svg>
  );
}

export function DashboardIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <rect x="3" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="3" width="7" height="7" rx="1.5" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" />
      <rect x="14" y="14" width="7" height="7" rx="1.5" />
    </Icon>
  );
}

export function WorkIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2" />
      <rect x="9" y="3" width="6" height="4" rx="1" />
      <path d="M8.5 12h7M8.5 16h5" />
    </Icon>
  );
}

export function SiteIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M4 20h16M6 20V9l6-4 6 4v11" />
      <path d="M9 20v-5h6v5M9.5 10.5h1M13.5 10.5h1" />
    </Icon>
  );
}

export function AcceptanceIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M7 4h10a2 2 0 0 1 2 2v14H5V6a2 2 0 0 1 2-2Z" />
      <path d="M9 3h6v4H9zM8.5 12l2 2 4-4M8.5 18h7" />
    </Icon>
  );
}

export function DocumentsIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M5 3.5h9l4 4V20.5H5z" />
      <path d="M14 3.5v4h4M8 12h7M8 15.5h7M8 19h4" />
    </Icon>
  );
}

export function ProjectIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M4 20V8l8-4 8 4v12" />
      <path d="M4 20h16M8 20v-6h8v6M8 10h.01M12 10h.01M16 10h.01" />
    </Icon>
  );
}

export function MenuIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M4 7h16M4 12h16M4 17h16" />
    </Icon>
  );
}

export function CloseIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="m6 6 12 12M18 6 6 18" />
    </Icon>
  );
}

export function ChevronDownIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="m6 9 6 6 6-6" />
    </Icon>
  );
}

export function ArrowRightIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M4 12h16M14 6l6 6-6 6" />
    </Icon>
  );
}

export function ArrowLeftIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M20 12H4M10 6l-6 6 6 6" />
    </Icon>
  );
}

export function LogoutIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M10 4H5v16h5M14 8l4 4-4 4M9 12h9" />
    </Icon>
  );
}

export function KeyIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <circle cx="8" cy="15" r="3" />
      <path d="m10.5 12.5 7-7M14 6l2 2M16.5 3.5l2 2" />
    </Icon>
  );
}

export function CheckCircleIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="m8 12 2.5 2.5L16 9" />
    </Icon>
  );
}

export function ClockIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </Icon>
  );
}

export function AlertTriangleIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M12 4 3.5 19h17z" />
      <path d="M12 9v4M12 16h.01" />
    </Icon>
  );
}

export function CameraIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M4 8h3l1.5-2h7L17 8h3v11H4z" />
      <circle cx="12" cy="13" r="3.5" />
    </Icon>
  );
}
