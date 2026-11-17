import bpy
prefs = bpy.context.preferences.addons["cycles"].preferences
for kind in ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"):
    try:
        prefs.compute_device_type = kind
    except TypeError:
        continue
    prefs.get_devices()
    devs = [(d.name, d.type) for d in prefs.devices if d.type == kind]
    print("DEVICES", kind, devs)
print("VERSION", bpy.app.version_string)
