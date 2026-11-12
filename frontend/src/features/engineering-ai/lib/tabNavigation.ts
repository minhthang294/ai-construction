/**
 * Returns the tab index that should receive focus for a horizontal tab list.
 * Returns null when the key is not part of the roving-tabindex pattern.
 */
export function nextTabIndex(
  currentIndex: number,
  key: string,
  count: number,
): number | null {
  if (count <= 0) return null;
  const index = Math.min(Math.max(currentIndex, 0), count - 1);
  switch (key) {
    case "ArrowRight":
      return (index + 1) % count;
    case "ArrowLeft":
      return (index - 1 + count) % count;
    case "Home":
      return 0;
    case "End":
      return count - 1;
    default:
      return null;
  }
}
