"""Build a stylized (chibi) TFT-style girl: long white hair, black clothes.
Exports liora.glb and liora.obj. Y up, character faces +Z."""
import numpy as np
import trimesh
from trimesh.creation import icosphere, cylinder, capsule, revolve
from trimesh.visual.material import PBRMaterial
from trimesh.visual import TextureVisuals

SKIN  = [245, 220, 203, 255]
HAIR  = [244, 246, 250, 255]
HAIR2 = [230, 234, 241, 255]
BLACK = [20, 20, 24, 255]
BELT  = [45, 45, 54, 255]
EYE   = [58, 58, 84, 255]
WHITE = [255, 255, 255, 255]
MOUTH = [181, 119, 110, 255]

def mat(name, rgba):
    return PBRMaterial(name=name, baseColorFactor=rgba, metallicFactor=0.0, roughnessFactor=0.9)

def paint(mesh, name, rgba):
    mesh.visual = TextureVisuals(material=mat(name, rgba))
    mesh.metadata["name"] = name
    return mesh

def T(mesh, x=0, y=0, z=0, sx=1, sy=1, sz=1, rx=0, ry=0, rz=0):
    m = mesh.copy()
    S = np.eye(4); S[0,0], S[1,1], S[2,2] = sx, sy, sz
    m.apply_transform(S)
    for ang, axis in ((rx,[1,0,0]),(ry,[0,1,0]),(rz,[0,0,1])):
        if ang:
            m.apply_transform(trimesh.transformations.rotation_matrix(np.radians(ang), axis))
    m.apply_translation([x, y, z])
    return m

def frustum(r_top, r_bot, h, y0, segments=32):
    # revolve profile in XY (x = radius), around Y
    prof = np.array([[0, y0], [r_bot, y0], [r_top, y0 + h], [0, y0 + h]])
    m = revolve(prof, sections=segments)
    m.apply_transform(trimesh.transformations.rotation_matrix(np.radians(-90), [1,0,0]))
    return m

parts = []
add = lambda m: parts.append(m)

# ---- proportions (units: 1.0 ≈ head width) : ~2.5 heads tall
HEAD_R = 0.42
HEAD_Y = 1.55

# head + neck
add(paint(T(icosphere(3, HEAD_R), y=HEAD_Y, sy=1.05), "head", SKIN))
add(paint(T(cylinder(0.11, 0.22, sections=16), y=HEAD_Y - 0.44, rx=90), "neck", SKIN))

# face
for sx in (-1, 1):
    add(paint(T(icosphere(2, 0.062), x=sx*0.15, y=HEAD_Y+0.02, z=HEAD_R-0.005, sz=0.45), f"eye_white_{sx}", WHITE))
    add(paint(T(icosphere(2, 0.042), x=sx*0.152, y=HEAD_Y+0.0, z=HEAD_R+0.02, sz=0.45), f"eye_{sx}", EYE))
    add(paint(T(icosphere(2, 0.014), x=sx*0.14, y=HEAD_Y+0.03, z=HEAD_R+0.045), f"eye_light_{sx}", WHITE))
add(paint(T(capsule(0.05, 0.012, count=[8,8]), y=HEAD_Y-0.19, z=HEAD_R*0.97, ry=90), "mouth", MOUTH))

# hair: cap (slightly bigger sphere, shifted back/up so the face shows)
add(paint(T(icosphere(3, HEAD_R+0.045), y=HEAD_Y+0.06, z=-0.11, sz=1.0), "hair_cap", HAIR))
# bangs: flattened cap over the forehead
add(paint(T(icosphere(3, HEAD_R+0.03), y=HEAD_Y+0.27, z=0.02, sy=0.42, sz=0.98), "hair_bangs", HAIR))
# long hair down the back to the hips (tapered)
add(paint(T(frustum(0.26, 0.36, 1.30, 0.0), y=0.32, z=-0.30, sx=0.9, sz=0.5), "hair_back", HAIR2))
# two front side locks
for sx in (-1, 1):
    add(paint(T(capsule(0.70, 0.07, count=[10,10]), x=sx*0.37, y=1.12, z=0.22, rx=90), f"hair_lock_{'L' if sx<0 else 'R'}", HAIR))

# black dress: shoulders -> hem, plus belt
add(paint(frustum(0.26, 0.46, 0.78, 0.36), "dress", BLACK))
add(paint(T(cylinder(0.335, 0.06, sections=32), y=0.78, rx=90), "belt", BELT))

# arms (black sleeves) + hands
for sx in (-1, 1):
    add(paint(T(capsule(0.55, 0.085, count=[10,10]), x=sx*0.36, y=0.80, rx=90, rz=sx*-12), f"arm_{'L' if sx<0 else 'R'}", BLACK))
    add(paint(T(icosphere(2, 0.085), x=sx*0.46, y=0.46), f"hand_{'L' if sx<0 else 'R'}", SKIN))

# legs + black boots
for sx in (-1, 1):
    add(paint(T(capsule(0.34, 0.08, count=[10,10]), x=sx*0.15, y=0.28, rx=90), f"leg_{'L' if sx<0 else 'R'}", SKIN))
    add(paint(T(capsule(0.22, 0.10, count=[10,10]), x=sx*0.15, y=0.12, rx=90), f"boot_{'L' if sx<0 else 'R'}", BLACK))
    add(paint(T(icosphere(2, 0.11), x=sx*0.15, y=0.06, z=0.05, sy=0.6, sz=1.3), f"boot_toe_{'L' if sx<0 else 'R'}", BLACK))

scene = trimesh.Scene()
for m in parts:
    scene.add_geometry(m, node_name=m.metadata["name"], geom_name=m.metadata["name"])

# ground the model at y=0
b = scene.bounds
scene.apply_translation([0, -b[0][1], 0])

scene.export("liora.glb")
merged = trimesh.util.concatenate(parts)
merged.export("liora.obj")
print("tris:", sum(len(m.faces) for m in parts), "height:", scene.bounds[1][1]-scene.bounds[0][1])
