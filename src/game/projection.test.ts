import { describe, expect, it } from "vitest";
import { homography, project, toMatrix3d, type Quad } from "./projection";

const close = (a: number, b: number) => expect(a).toBeCloseTo(b, 6);

// A trapezoid: narrower at the top like a floor seen from the front.
const QUAD: Quad = { tl: [30, 20], tr: [70, 20], br: [90, 80], bl: [10, 80] };

describe("homography", () => {
  it("maps the four corners of a w×h rectangle onto the quad", () => {
    const H = homography(7, 6, QUAD);
    let p = project(H, 0, 0); close(p[0], 30); close(p[1], 20);
    p = project(H, 7, 0); close(p[0], 70); close(p[1], 20);
    p = project(H, 7, 6); close(p[0], 90); close(p[1], 80);
    p = project(H, 0, 6); close(p[0], 10); close(p[1], 80);
  });
  it("keeps straight lines straight: the centre column stays on the quad's vertical midline", () => {
    const H = homography(7, 6, QUAD);
    for (const y of [0, 1.5, 3, 4.5, 6]) close(project(H, 3.5, y)[0], 50);
  });
  it("is the identity when the quad is the rectangle itself", () => {
    const H = homography(4, 2, { tl: [0, 0], tr: [4, 0], br: [4, 2], bl: [0, 2] });
    const p = project(H, 1.25, 0.5); close(p[0], 1.25); close(p[1], 0.5);
  });
  it("front rows are wider than back rows", () => {
    const H = homography(7, 6, QUAD);
    const back = project(H, 1, 0.5)[0] - project(H, 0, 0.5)[0];
    const front = project(H, 1, 5.5)[0] - project(H, 0, 5.5)[0];
    expect(front).toBeGreaterThan(back);
  });
});

describe("toMatrix3d", () => {
  it("produces a CSS matrix3d() with the homography in the x, y and w rows", () => {
    const H = homography(4, 2, { tl: [0, 0], tr: [4, 0], br: [4, 2], bl: [0, 2] });
    const css = toMatrix3d(H);
    expect(css.startsWith("matrix3d(")).toBe(true);
    const n = css.slice(9, -1).split(",").map(Number);
    expect(n).toHaveLength(16);
    // Identity homography → identity matrix.
    close(n[0], 1); close(n[5], 1); close(n[10], 1); close(n[15], 1);
    close(n[3], 0); close(n[7], 0); close(n[12], 0); close(n[13], 0);
  });
});
