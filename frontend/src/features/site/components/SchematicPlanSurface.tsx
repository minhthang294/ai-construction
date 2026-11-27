/** Static schematic grid behind the interactive marker layer. */

import type { ImageBox } from "../lib/drawingMap";
import type { SchematicPlan } from "../lib/schematicMap";

export default function SchematicPlanSurface({
  plan,
  box,
}: {
  plan: SchematicPlan;
  box: ImageBox;
}) {
  const firstX = plan.axes[0]?.x ?? 0;
  const lastX = plan.axes[plan.axes.length - 1]?.x ?? 0;
  const firstY = plan.rows[0]?.y ?? 0;
  const lastY = plan.rows[plan.rows.length - 1]?.y ?? 0;
  const bubbleY = Math.max(16, firstY - 26);
  return (
    <div
      className="absolute"
      style={{
        left: box.left,
        top: box.top,
        width: box.width,
        height: box.height,
      }}
    >
      <svg
        viewBox={`0 0 ${plan.width} ${plan.height}`}
        preserveAspectRatio="none"
        className="absolute inset-0 h-full w-full"
        aria-hidden="true"
        focusable="false"
      >
        <rect width={plan.width} height={plan.height} fill="#f8fafc" />
        {plan.bunke ? (
          <rect
            x={plan.bunke.x0}
            y={plan.bunke.y0}
            width={plan.bunke.x1 - plan.bunke.x0}
            height={plan.bunke.y1 - plan.bunke.y0}
            rx={10}
            fill="#f1f5f9"
            stroke="#94a3b8"
            strokeDasharray="7 5"
            strokeWidth={1.2}
          />
        ) : null}
        {plan.bunke ? (
          <text
            x={plan.bunke.x0 + 8}
            y={plan.bunke.y0 - 6}
            fontSize={12}
            fontWeight={700}
            fill="#475569"
          >
            Bunke
          </text>
        ) : null}
        {plan.axes.map((axis) => (
          <g key={`axis-${axis.value}`}>
            <line
              x1={axis.x}
              y1={bubbleY}
              x2={axis.x}
              y2={lastY + 18}
              stroke="#e2e8f0"
              strokeWidth={0.8}
            />
            <circle
              cx={axis.x}
              cy={bubbleY}
              r={12}
              fill="#ffffff"
              stroke="#94a3b8"
              strokeWidth={1}
            />
            <text
              x={axis.x}
              y={bubbleY + 3.5}
              fontSize={9}
              textAnchor="middle"
              fill="#334155"
            >
              {axis.value}
            </text>
          </g>
        ))}
        {plan.rows.map((row) => (
          <g key={`row-${row.key}`}>
            <line
              x1={!row.main && plan.bunke ? plan.bunke.x0 : firstX - 10}
              y1={row.y}
              x2={!row.main && plan.bunke ? plan.bunke.x1 : lastX + 10}
              y2={row.y}
              stroke={row.main ? "#cbd5e1" : "#dbe3ec"}
              strokeWidth={row.main ? 1.2 : 1}
              strokeDasharray={row.main ? undefined : "5 4"}
            />
            <circle
              cx={26}
              cy={row.y}
              r={13}
              fill={row.main ? "#0f172a" : "#e2e8f0"}
              stroke="#94a3b8"
              strokeWidth={1}
            />
            <text
              x={26}
              y={row.y + 4}
              fontSize={11}
              fontWeight={700}
              textAnchor="middle"
              fill={row.main ? "#ffffff" : "#334155"}
            >
              {row.key}
            </text>
          </g>
        ))}
        {plan.bunkeGap ? (
          <text
            x={firstX - 8}
            y={lastY + 34}
            fontSize={10}
            fill="#64748b"
          >
            Bunke tách trục
          </text>
        ) : null}
      </svg>
    </div>
  );
}
