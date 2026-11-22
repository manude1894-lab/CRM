import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("../api/client", () => ({ API_URL: "http://api.test/api/v1" }));

describe("reportError", () => {
  beforeEach(() => vi.resetModules());
  it("posts the page and error once, and returns the reference", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ reference: "ABC123" }) });
    globalThis.fetch = fetchMock;
    const { reportError } = await import("./reportError");
    const err = new ReferenceError("people is not defined");
    expect(await reportError("dashboard", err)).toBe("ABC123");
    expect(await reportError("dashboard", err)).toBe(null); // the same error again is not re-sent
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toBe("http://api.test/api/v1/system/client-errors");
    expect(JSON.parse(opts.body)).toMatchObject({ where: "dashboard", error_type: "ReferenceError", message: "people is not defined" });
  });
  it("never throws when the server cannot be reached", async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error("offline"));
    const { reportError } = await import("./reportError");
    expect(await reportError("x", new Error("y"))).toBe(null);
  });
});
