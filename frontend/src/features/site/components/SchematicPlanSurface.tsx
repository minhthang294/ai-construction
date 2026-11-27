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
  const mainLastY = plan.rows
    .filter((row) => row.main)
    .reduce((max, row) => Math.max(max, row.y), firstY);
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
        {plan.bunkeBlocks.map((block, index) => (
          <g key={`bunke-block-${index}`}>
            <rect
              x={block.x0}
              y={block.y0}
              width={block.x1 - block.x0}
              height={block.y1 - block.y0}
              rx={8}
              fill="#f1f5f9"
              stroke="#94a3b8"
              strokeDasharray="7 5"
              strokeWidth={1}
            />
            {index === 0 ? (
              <text
                x={block.x0 + 6}
                y={block.y0 - 5}
                fontSize={11}
                fontWeight={700}
                fill="#475569"
              >
                Bunke
              </text>
            ) : null}
          </g>
        ))}
        {plan.axes.map((axis) => (
          <g key={`axis-${axis.value}`}>
            <line
              x1={axis.x}
              y1={bubbleY}
              x2={axis.x}
              y2={mainLastY + 14}
              stroke="#eef2f7"
              strokeWidth={0.6}
            />
            <circle
              cx={axis.x}
              cy={bubbleY}
              r={8}
              fill="#ffffff"
              stroke="#cbd5e1"
              strokeWidth={0.7}
            />
            <text
              x={axis.x}
              y={bubbleY + 2.5}
              fontSize={6.5}
              textAnchor="middle"
              fill="#64748b"
            >
              {axis.value}
            </text>
          </g>
        ))}
        {plan.bunkeBlocks.map((block, blockIndex) =>
          block.axes.map((axis) => (
            <g key={`bunke-axis-${blockIndex}-${axis.value}`}>
              <line
                x1={axis.x}
                y1={block.y0}
                x2={axis.x}
                y2={block.y1}
                stroke="#eef2f7"
                strokeWidth={0.6}
              />
              <circle
                cx={axis.x}
                cy={block.y0 + 10}
                r={6}
                fill="#ffffff"
                stroke="#cbd5e1"
                strokeWidth={0.6}
              />
              <text
                x={axis.x}
                y={block.y0 + 11}
                fontSize={5}
                textAnchor="middle"
                fill="#64748b"
              >
                {axis.value}
              </text>
            </g>
          )),
        )}
        {plan.rows.map((row) => (
          <g key={`row-${row.key}`}>
            {row.main ? (
              <line
                x1={firstX - 10}
                y1={row.y}
                x2={lastX + 10}
                y2={row.y}
                stroke="#e2e8f0"
                strokeWidth={0.9}
              />
            ) : (
              plan.bunkeBlocks
                .filter((block) => block.rows.includes(row.key))
                .map((block, blockIndex) => (
                  <line
                    key={`row-${row.key}-block-${blockIndex}`}
                    x1={block.x0}
                    y1={row.y}
                    x2={block.x1}
                    y2={row.y}
                    stroke="#e8eef5"
                    strokeWidth={0.8}
                    strokeDasharray="5 4"
                  />
                ))
            )}
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
      </svg>
    </div>
  );
}
