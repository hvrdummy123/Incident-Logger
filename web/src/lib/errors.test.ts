import { describe, expect, it } from "vitest";
import { problemToMessage } from "./errors";

describe("problemToMessage", () => {
  it("maps problem+json style errors", () => {
    expect(
      problemToMessage({ title: "Bad Request", detail: "File looks binary." }),
    ).toBe("Bad Request: File looks binary.");
  });
});
