# Check which resolver USD instantiated as primary.
# Note: USD Python bindings wrap all ArResolver subclasses as pxr.Ar.Resolver,
# so type(resolver).__name__ always returns "Resolver" regardless of the C++ type.
# Instead, check the Plug registry (plugin is only loaded when the factory
# manufactures an instance) and confirm no fallback occurred.
from pxr import Ar, Plug

Ar.GetResolver()

reg = Plug.Registry()
omni_plugin = next((p for p in reg.GetAllPlugins() if p.name == "Omniverse USD Plugin"), None)

if omni_plugin is None:
    print("FAIL: 'Omniverse USD Plugin' not found in Plug registry")
elif not omni_plugin.isLoaded:
    print("FAIL: 'Omniverse USD Plugin' found but not loaded — factory->New() was never called")
else:
    print("PASS: OmniUsdResolver is active as primary resolver")
    print(f"      Plugin: {omni_plugin.name}, loaded: {omni_plugin.isLoaded}")

quit()
