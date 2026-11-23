export default function BatchZoneBadge({
  zone,
  segmentNumber,
  primaryZone,
}: {
  zone: string;
  segmentNumber: number;
  primaryZone?: string | null;
}) {
  if (!primaryZone || zone === primaryZone) return null;
  return (
    <span className="inline-flex max-w-full break-words rounded-full border border-violet-200 bg-violet-50 px-2 py-0.5 text-[11px] font-medium text-violet-900">
      {zone} PĐ{segmentNumber} · thi công cùng đợt
    </span>
  );
}
