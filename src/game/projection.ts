/**
 * Plane projection for painted arenas: fits the w×h grid onto the quadrilateral where the map's
 * floor sits in the image, so cells and unit positions follow the painting's perspective.
 */
export type Point = [number, number];
export interface Quad {
  tl: Point;
  tr: Point;
  br: Point;
  bl: Point;
}
/** 3×3 homography, row-major, normalised so h[8] === 1. */
export type Homography = number[];

/** Solves A·x = b for an n×n system by Gaussian elimination with partial pivoting. */
function solve(A: number[][], b: number[]): number[] {
  const n = b.length;
  const M = A.map((row, i) => [...row, b[i]]);
  for (let c = 0; c < n; c++) {
    let p = c;
    for (let r = c + 1; r < n; r++) if (Math.abs(M[r][c]) > Math.abs(M[p][c])) p = r;
    [M[c], M[p]] = [M[p], M[c]];
    const pivot = M[c][c];
    for (let k = c; k <= n; k++) M[c][k] /= pivot;
    for (let r = 0; r < n; r++) {
      if (r === c) continue;
      const f = M[r][c];
      for (let k = c; k <= n; k++) M[r][k] -= f * M[c][k];
    }
  }
  return M.map((row) => row[n]);
}

/** Homography that sends the rectangle (0,0)–(w,h) to `quad` (tl, tr, br, bl in that order). */
export function homography(w: number, h: number, quad: Quad): Homography {
  const src: Point[] = [[0, 0], [w, 0], [w, h], [0, h]];
  const dst: Point[] = [quad.tl, quad.tr, quad.br, quad.bl];
  const A: number[][] = [];
  const b: number[] = [];
  for (let i = 0; i < 4; i++) {
    const [x, y] = src[i];
    const [u, v] = dst[i];
    A.push([x, y, 1, 0, 0, 0, -u * x, -u * y]);
    b.push(u);
    A.push([0, 0, 0, x, y, 1, -v * x, -v * y]);
    b.push(v);
  }
  return [...solve(A, b), 1];
}

/** Projects a grid point through the homography. */
export function project(H: Homography, x: number, y: number): Point {
  const w = H[6] * x + H[7] * y + H[8];
  return [(H[0] * x + H[1] * y + H[2]) / w, (H[3] * x + H[4] * y + H[5]) / w];
}

/** The same homography as a CSS transform (column-major matrix3d, transform-origin 0 0). */
export function toMatrix3d(H: Homography): string {
  const m = [H[0], H[3], 0, H[6], H[1], H[4], 0, H[7], 0, 0, 1, 0, H[2], H[5], 0, H[8]];
  return `matrix3d(${m.map((v) => +v.toFixed(8)).join(",")})`;
}
