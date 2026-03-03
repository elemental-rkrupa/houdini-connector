# Check which resolver USD instantiated as primary.
# This is the key test for the current blocker: if TF_REGISTRY_FUNCTION
# never fires, factory->New() is never registered and USD falls back to
# ArDefaultResolver instead of OmniUsdResolver.
from pxr import Ar

resolver = Ar.GetResolver()
resolver_type = type(resolver).__name__

print(f"Resolver type: {resolver_type}")

if resolver_type == "OmniUsdResolver":
    print("PASS: OmniUsdResolver is active as primary resolver")
else:
    print(f"FAIL: Expected OmniUsdResolver, got {resolver_type}")
    print("      This means factory->New() was never registered.")
    print("      Check TF_DEBUG output for 'Failed to manufacture' or 'Using default asset resolver'.")

quit()
