/**
 * Feature-local presentation tokens for Engineering AI.
 *
 * The SBTECH palette is duplicated here (blue, red, ink) until the shared
 * application tokens land. Keeping the values in one module makes the feature
 * easy to retarget without touching shared styles or components.
 */
export const BRAND_BLUE = "#405e9b";
export const BRAND_BLUE_DARK = "#344c7e";
export const BRAND_RED = "#e5322c";
export const BRAND_INK = "#1b1a16";

export const FOCUS_RING =
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#405e9b] focus-visible:ring-offset-2 focus-visible:ring-offset-white";

export function cx(
  ...values: Array<string | false | null | undefined>
): string {
  return values.filter(Boolean).join(" ");
}

export const CARD = "rounded-xl border border-slate-200 bg-white shadow-sm";
export const CARD_PAD = "p-4 sm:p-5";
export const SECTION_TITLE =
  "text-base font-semibold tracking-tight text-slate-950 sm:text-lg";
export const SECTION_TEXT = "text-sm leading-6 text-slate-600";
export const META_TEXT = "text-xs leading-5 text-slate-600";
export const LABEL = "block text-sm font-medium text-slate-800";
export const HELP_TEXT = "mt-1 text-xs leading-5 text-slate-500";

export const FIELD_BASE =
  "min-h-11 w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-base text-slate-900 shadow-sm placeholder:text-slate-400 focus:border-[#405e9b] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#405e9b]/30 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-500 sm:text-sm";

export const FIELD = "mt-1.5 " + FIELD_BASE;

export const FIELD_INLINE =
  "min-h-11 rounded-lg border border-slate-300 bg-white px-3 py-2 text-base text-slate-900 shadow-sm focus:border-[#405e9b] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#405e9b]/30 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-500 sm:text-sm";

export const SELECT_INLINE = FIELD_INLINE;

export const BUTTON_BASE =
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50 " +
  FOCUS_RING;

export const BUTTON_PRIMARY =
  BUTTON_BASE +
  " bg-[#405e9b] text-white shadow-sm hover:bg-[#344c7e] active:bg-[#2c416b]";

export const BUTTON_SECONDARY =
  BUTTON_BASE +
  " border border-slate-300 bg-white text-slate-700 shadow-sm hover:border-[#405e9b]/60 hover:bg-slate-50 hover:text-[#35507f]";

export const BUTTON_DANGER =
  BUTTON_BASE + " bg-[#c4241f] text-white shadow-sm hover:bg-[#a51f1b]";

export const BUTTON_DANGER_OUTLINE =
  BUTTON_BASE +
  " border border-red-300 bg-white text-red-700 hover:bg-red-50";

export const BUTTON_SUCCESS =
  BUTTON_BASE +
  " bg-emerald-700 text-white shadow-sm hover:bg-emerald-800 disabled:bg-emerald-700";

export const BUTTON_WARNING =
  BUTTON_BASE +
  " border border-amber-300 bg-amber-50 text-amber-950 hover:bg-amber-100";

export const BADGE =
  "inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium";

export const PANEL_ALERT =
  "rounded-lg border border-red-200 bg-red-50 p-3 text-sm leading-6 text-red-800";
export const PANEL_NOTE =
  "rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm leading-6 text-amber-950";
export const PANEL_EMPTY =
  "rounded-lg border border-dashed border-slate-300 bg-slate-50 p-4 text-sm leading-6 text-slate-600";
