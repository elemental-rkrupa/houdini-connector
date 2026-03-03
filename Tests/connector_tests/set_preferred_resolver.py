# Simulate the sequence that happens at Houdini startup:
#   1. ArSetPreferredResolver("OmniUsdResolver")  [done by 456.py]
#   2. Ar.GetResolver()                           [called by USD on first path resolution]
#
# This test verifies that explicitly setting the preferred resolver and
# then instantiating it succeeds. It isolates the 456.py path from any
# timing concerns and confirms whether the factory is registered at all.
#
# Expected:  PASS — resolver type is OmniUsdResolver
# Current:   FAIL — factory->New() never registered (.pxrctor blocker)
from pxr import Ar

print("Calling ArSetPreferredResolver('OmniUsdResolver')...")
Ar.SetPreferredResolver("OmniUsdResolver")

print("Calling Ar.GetResolver()...")
resolver = Ar.GetResolver()
resolver_type = type(resolver).__name__

print(f"Resolver type: {resolver_type}")

if resolver_type == "OmniUsdResolver":
    print("PASS: OmniUsdResolver instantiated correctly after SetPreferredResolver")
else:
    print(f"FAIL: Got {resolver_type} after SetPreferredResolver('OmniUsdResolver')")
    print("      The preferred resolver was accepted but factory->New() returned null.")
    print("      See debugging.md Option B: register factory via static initialiser.")

quit()
