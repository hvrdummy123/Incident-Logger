/** j/k list navigation; / focuses search; Enter activates selection. */
export function nextIndex(
  current: number,
  key: string,
  length: number,
): number {
  if (length <= 0) return -1;
  if (key === "j" || key === "ArrowDown") return Math.min(length - 1, Math.max(0, current) + 1);
  if (key === "k" || key === "ArrowUp") return Math.max(0, (current < 0 ? 0 : current) - 1);
  return current;
}

export function isTypingTarget(el: EventTarget | null): boolean {
  if (!(el instanceof HTMLElement)) return false;
  const tag = el.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || el.isContentEditable;
}
