// Rotates every root node of a glTF scene about the Y axis. Usage: node scripts/rotate-glb.mjs in.glb out.glb <degrees>
import { NodeIO } from "@gltf-transform/core";
import { ALL_EXTENSIONS } from "@gltf-transform/extensions";

const [input, output, degrees] = process.argv.slice(2);
if (!input || !output || degrees === undefined) {
  console.error("usage: node scripts/rotate-glb.mjs in.glb out.glb <degrees>");
  process.exit(1);
}
const half = (Number(degrees) * Math.PI) / 360;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS);
const doc = await io.read(input);
for (const scene of doc.getRoot().listScenes()) {
  for (const node of scene.listChildren()) {
    // Quaternion for a rotation of `degrees` about +Y, composed before the node's own rotation.
    const [x, y, z, w] = node.getRotation();
    const s = Math.sin(half), c = Math.cos(half);
    // q = (0, s, 0, c) * (x, y, z, w)
    node.setRotation([
      c * x + s * z,
      c * y + s * w,
      c * z - s * x,
      c * w - s * y,
    ]);
  }
}
await io.write(output, doc);
console.log(`rotated ${input} by ${degrees}° → ${output}`);
