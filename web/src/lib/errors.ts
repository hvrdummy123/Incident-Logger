export type Problem = {
  title: string;
  detail?: string;
  status?: number;
};

export function problemToMessage(err: unknown): string {
  if (err && typeof err === "object") {
    const p = err as Problem & { message?: string };
    if (p.detail) return `${p.title ?? "Error"}: ${p.detail}`;
    if (p.title) return p.title;
    if (p.message) return p.message;
  }
  if (typeof err === "string") return err;
  return "Something went wrong. Retry, or check the API is running.";
}
