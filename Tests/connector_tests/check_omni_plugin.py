# Check that the Omniverse USD Plugin is known to USD's Plug registry
# and that it loaded successfully.
#
# 'found but not loaded' means plugInfo.json was discovered but the DLL
# either could not be found on PATH or failed during DLL load (static init crash,
# missing dependency, wrong USD namespace).
#
# 'not found' means PXR_PLUGINPATH_NAME / HOUDINI_USD_DSO_PATH is not pointing
# at the right resources folder.
from pxr import Plug

TARGET = "Omniverse USD Plugin"

reg = Plug.Registry()
plugins = {p.name: p for p in reg.GetAllPlugins()}

plugin = plugins.get(TARGET)

if plugin is None:
    print(f"FAIL: '{TARGET}' not found in USD plugin registry")
    print("      Check HOUDINI_USD_DSO_PATH points to the resolver resources folder.")
elif plugin.isLoaded:
    print(f"PASS: '{TARGET}' found and loaded")
else:
    print(f"FAIL: '{TARGET}' found in registry but isLoaded = False")
    print("      The DLL was not loaded. Check PATH includes omni_usd_resolver/ and HOUDINI_BIN.")
    print("      Enable TF_DEBUG=PLUG_LOAD for details.")

# Also print all omni-related plugins for context
print("\nAll omni-related plugins:")
for name, p in sorted(plugins.items()):
    if "omni" in name.lower():
        print(f"  {name}  isLoaded={p.isLoaded}")

quit()
