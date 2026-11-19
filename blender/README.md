# Product video studio (Blender)

`product_studio_setup.py` lists the open scene, backs it up, clears it, and builds a 4:5 product-video studio.

**Run:** Blender → Scripting tab → Open → `product_studio_setup.py` → Run Script.
The inventory and summary print to the system console.

**Warning:** this deletes everything in the current scene. If the file has been saved before, the script
first writes `<name>_before_studio.blend` next to it.

Settings (product height, light power, lens, backdrop size) are constants at the top of the script.
`preview.png` is a Cycles test render with a placeholder sphere.
