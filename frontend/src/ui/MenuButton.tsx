import { useEffect, useId, useRef, useState } from "react";
import type { ReactNode } from "react";

type Props = {
  label: ReactNode;
  children: ReactNode;
  /** Wrapper (positioning) classes. */
  className?: string;
  triggerClassName?: string;
  panelClassName?: string;
};

/**
 * Click-to-open popover used for action menus.
 *
 * Native `<details>/<summary>` only closes when its summary is clicked again,
 * which stranded the menu open after an outside tap. This component closes on
 * outside pointer-down (mouse and touch), on Escape (returning focus to the
 * trigger) and after any action inside the panel.
 */
export default function MenuButton({
  label,
  children,
  className = "",
  triggerClassName = "",
  panelClassName = "",
}: Props) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelId = useId();

  useEffect(() => {
    if (!open) return;

    function handlePointerDown(event: PointerEvent) {
      const target = event.target as Node | null;
      if (target && containerRef.current?.contains(target)) return;
      setOpen(false);
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      setOpen(false);
      triggerRef.current?.focus();
    }

    document.addEventListener("pointerdown", handlePointerDown, true);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown, true);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open]);

  return (
    <div ref={containerRef} className={`relative ${className}`.trim()}>
      <button
        ref={triggerRef}
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((value) => !value)}
        className={triggerClassName}
      >
        {label}
      </button>
      {open && (
        <div
          id={panelId}
          className={`absolute z-20 mt-1 ${panelClassName}`.trim()}
          onClick={() => setOpen(false)}
        >
          {children}
        </div>
      )}
    </div>
  );
}
