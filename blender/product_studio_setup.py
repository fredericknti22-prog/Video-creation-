"""
Product-video studio setup for Blender (4.x / 5.x).

What it does, in order:
  1. Lists everything in the open scene (objects, collections, materials, etc.)
  2. Saves a backup copy of the current .blend (if it has been saved before)
  3. Clears the scene
  4. Sets units (cm), frame size (1080 x 1350, 4:5) and 30 fps
  5. Builds a simple studio: curved white cyclorama backdrop, soft key light
     from the left, thin rim light from behind, camera at product height

Run it: Blender > Scripting tab > Open this file > Run Script
   or:  blender yourfile.blend --python product_studio_setup.py

The report is printed to the system console (Window > Toggle System Console
on Windows; the terminal that launched Blender on macOS/Linux).
"""

import math
import os

import bmesh
import bpy
from mathutils import Vector

# --------------------------------------------------------------------------
# Settings (all distances in metres internally; displayed as cm)
# --------------------------------------------------------------------------
RES_X, RES_Y, FPS = 1080, 1350, 30

PRODUCT_HEIGHT = 0.15          # centre of a typical tabletop product (15 cm)

BACKDROP_WIDTH = 4.0           # left-right (X)
FLOOR_FRONT = 2.0              # how far the floor runs toward the camera
FLOOR_TO_CURVE = 1.0           # product (origin) to where the floor starts bending
CURVE_RADIUS = 0.8             # radius of the floor-to-wall sweep
WALL_HEIGHT = 2.5
CURVE_SEGMENTS = 24

CAMERA_DISTANCE = 1.4
CAMERA_LENS_MM = 85            # flattering, low-distortion product lens

MAKE_BACKUP = True


# --------------------------------------------------------------------------
# 1. Inventory
# --------------------------------------------------------------------------
def list_scene(scene):
    lines = [f"=== Scene '{scene.name}' inventory ==="]
    objs = list(scene.objects)
    lines.append(f"Objects ({len(objs)}):")
    for o in objs:
        loc = ", ".join(f"{v:.3f}" for v in o.location)
        extra = ""
        if o.type == "MESH" and o.data:
            extra = f" verts={len(o.data.vertices)}"
            mats = [m.name for m in o.data.materials if m]
            if mats:
                extra += f" materials={mats}"
        elif o.type == "LIGHT":
            extra = f" {o.data.type} {o.data.energy:.0f}W"
        elif o.type == "CAMERA":
            extra = f" lens={o.data.lens:.0f}mm"
        parent = f" parent={o.parent.name}" if o.parent else ""
        lines.append(f"  - {o.name} [{o.type}] loc=({loc}){extra}{parent}")

    def names(coll):
        return ", ".join(sorted(i.name for i in coll)) or "(none)"

    lines.append(f"Collections: {names(scene.collection.children_recursive)}")
    for label, coll in (
        ("Materials", bpy.data.materials),
        ("Meshes", bpy.data.meshes),
        ("Lights", bpy.data.lights),
        ("Cameras", bpy.data.cameras),
        ("Images", bpy.data.images),
        ("Node groups", bpy.data.node_groups),
        ("Worlds", bpy.data.worlds),
        ("Actions", bpy.data.actions),
    ):
        lines.append(f"{label} ({len(coll)}): {names(coll)}")
    r = scene.render
    lines.append(
        f"Render: {r.resolution_x}x{r.resolution_y} @ {r.resolution_percentage}%, "
        f"{r.fps / r.fps_base:g} fps, engine={r.engine}, "
        f"units={scene.unit_settings.system}/{scene.unit_settings.length_unit}"
    )
    report = "\n".join(lines)
    print(report)
    return report


# --------------------------------------------------------------------------
# 2-3. Backup and clear
# --------------------------------------------------------------------------
def backup_file():
    path = bpy.data.filepath
    if not path:
        print("Backup skipped: file has never been saved.")
        return None
    root, ext = os.path.splitext(path)
    backup = f"{root}_before_studio{ext}"
    bpy.ops.wm.save_as_mainfile(filepath=backup, copy=True)
    print(f"Backup saved: {backup}")
    return backup


def clear_scene(scene):
    for obj in list(scene.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for coll in list(scene.collection.children_recursive):
        bpy.data.collections.remove(coll)
    bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)


# --------------------------------------------------------------------------
# 4. Scene settings
# --------------------------------------------------------------------------
def configure_scene(scene):
    us = scene.unit_settings
    us.system = "METRIC"
    us.length_unit = "CENTIMETERS"
    # Keep scale at 1.0 so 1 unit stays 1 metre internally: light falloff,
    # physics and clipping keep real-world behaviour, the UI just shows cm.
    us.scale_length = 1.0

    r = scene.render
    r.resolution_x, r.resolution_y = RES_X, RES_Y
    r.resolution_percentage = 100
    r.pixel_aspect_x = r.pixel_aspect_y = 1.0
    r.fps, r.fps_base = FPS, 1.0


# --------------------------------------------------------------------------
# 5. Studio
# --------------------------------------------------------------------------
def new_collection(scene, name):
    coll = bpy.data.collections.new(name)
    scene.collection.children.link(coll)
    return coll


def cyclorama_profile():
    """(y, z) points: floor -> quarter-circle sweep -> wall. +Y is the wall."""
    pts = [(-FLOOR_FRONT, 0.0)]
    cy, cz = FLOOR_TO_CURVE, CURVE_RADIUS        # centre of the bend
    for i in range(CURVE_SEGMENTS + 1):
        a = -math.pi / 2 + (math.pi / 2) * i / CURVE_SEGMENTS
        pts.append((cy + CURVE_RADIUS * math.cos(a), cz + CURVE_RADIUS * math.sin(a)))
    pts.append((FLOOR_TO_CURVE + CURVE_RADIUS, WALL_HEIGHT))
    return pts


def build_backdrop(coll):
    mesh = bpy.data.meshes.new("Cyclorama")
    bm = bmesh.new()
    half = BACKDROP_WIDTH / 2
    left = [bm.verts.new((-half, y, z)) for y, z in cyclorama_profile()]
    right = [bm.verts.new((half, y, z)) for y, z in cyclorama_profile()]
    for i in range(len(left) - 1):
        bm.faces.new((left[i], right[i], right[i + 1], left[i + 1]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    for p in mesh.polygons:
        p.use_smooth = True

    obj = bpy.data.objects.new("Backdrop", mesh)
    coll.objects.link(obj)

    mat = bpy.data.materials.new("Backdrop_White")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (0.9, 0.9, 0.9, 1.0)  # not 1.0: avoids clipping
    bsdf.inputs["Roughness"].default_value = 0.6
    mesh.materials.append(mat)
    return obj


def aim(obj, target):
    con = obj.constraints.new("TRACK_TO")
    con.target = target
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"


def add_area_light(coll, name, location, target, energy, shape, size, size_y=None):
    data = bpy.data.lights.new(name, "AREA")
    data.energy = energy
    data.shape = shape
    data.size = size
    if size_y is not None:
        data.size_y = size_y
    obj = bpy.data.objects.new(name, data)
    obj.location = location
    obj.visible_camera = False           # light panels never show in shot
    coll.objects.link(obj)
    aim(obj, target)
    return obj


def build_studio(scene):
    studio = new_collection(scene, "Studio")
    lights = new_collection(scene, "Lights")
    cams = new_collection(scene, "Camera")

    build_backdrop(studio)

    target = bpy.data.objects.new("Product_Target", None)
    target.empty_display_type = "PLAIN_AXES"
    target.empty_display_size = 0.05
    target.location = (0, 0, PRODUCT_HEIGHT)
    studio.objects.link(target)

    # Soft key: big square panel, camera-left, slightly forward and above.
    add_area_light(lights, "Key_Left", (-1.2, -0.8, 0.9), target,
                   energy=120, shape="SQUARE", size=1.5)
    # Thin rim: narrow vertical strip behind and to the right, for edge highlights.
    add_area_light(lights, "Rim_Back", (0.6, 0.7, 0.6), target,
                   energy=150, shape="RECTANGLE", size=0.08, size_y=1.2)

    cam_data = bpy.data.cameras.new("Product_Cam")
    cam_data.lens = CAMERA_LENS_MM
    cam_data.sensor_fit = "AUTO"
    cam_data.clip_start = 0.01
    cam_data.clip_end = 50
    cam = bpy.data.objects.new("Product_Cam", cam_data)
    cam.location = (0, -CAMERA_DISTANCE, PRODUCT_HEIGHT)
    cams.objects.link(cam)
    aim(cam, target)
    scene.camera = cam

    world = scene.world or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.05, 0.05, 0.05, 1.0)
        bg.inputs["Strength"].default_value = 0.3


# --------------------------------------------------------------------------
def summary(scene):
    r = scene.render
    lines = [
        "=== Studio set ===",
        f"- Units: metric, shown in centimetres (scale 1.0)",
        f"- Frame: {r.resolution_x} x {r.resolution_y} (4:5) at 100%",
        f"- Frame rate: {r.fps / r.fps_base:g} fps",
        f"- Backdrop: white cyclorama {BACKDROP_WIDTH*100:.0f} cm wide, "
        f"{CURVE_RADIUS*100:.0f} cm floor-to-wall curve, {WALL_HEIGHT*100:.0f} cm high",
        "- Key light: 150 x 150 cm area, 120 W, front-left, aimed at product",
        "- Rim light: 8 x 120 cm strip, 150 W, behind-right, aimed at product",
        f"- Camera: {CAMERA_LENS_MM} mm, {PRODUCT_HEIGHT*100:.0f} cm high, "
        f"{CAMERA_DISTANCE*100:.0f} cm from product, tracking 'Product_Target'",
        "- World: dark grey, low strength (lights do the work)",
    ]
    text = "\n".join(lines)
    print(text)
    return text


def main():
    scene = bpy.context.scene
    list_scene(scene)
    if MAKE_BACKUP:
        backup_file()
    clear_scene(scene)
    configure_scene(scene)
    build_studio(scene)
    summary(scene)


if __name__ == "__main__":
    main()
