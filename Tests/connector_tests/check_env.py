# Verify the connector environment is set up correctly before running
# resolver tests. Checks key environment variables and that critical
# files (DLL, plugInfo.json) exist at the expected paths.
import os
from pathlib import Path

PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"

results = []

def check_var(name, required=True):
    val = os.environ.get(name, "")
    if val:
        results.append((PASS, f"{name} = {val}"))
    elif required:
        results.append((FAIL, f"{name} is not set"))
    else:
        results.append((WARN, f"{name} is not set (optional)"))
    return val

def check_path_in_var(var_name, fragment):
    val = os.environ.get(var_name, "")
    if fragment.lower() in val.lower():
        results.append((PASS, f"{var_name} contains '{fragment}'"))
    else:
        results.append((FAIL, f"{var_name} does not contain '{fragment}'"))
        results.append((None,  f"       Value: {val}"))

def check_file(path, label):
    p = Path(path)
    if p.exists():
        results.append((PASS, f"{label} exists: {p}"))
    else:
        results.append((FAIL, f"{label} not found: {p}"))

# --- Environment variables ---
omni_root = check_var("OMNI_ROOT")
check_var("HOMNI")
check_var("HOUDINI_PATH")
check_var("HOUDINI_USD_DSO_PATH")
check_var("HOUDINI_BIN")
homni_conn = check_var("HOMNI_DEFAULT_CONNECTIONS", required=False)
if homni_conn:
    results.append((WARN, "HOMNI_DEFAULT_CONNECTIONS is set — may cause UI hang if server unreachable"))

# --- Critical files ---
if omni_root:
    check_file(
        Path(omni_root) / "omni_usd_resolver" / "omni_usd_resolver.dll",
        "omni_usd_resolver.dll"
    )
    check_file(
        Path(omni_root) / "omni_usd_resolver" / "usd" / "omniverse" / "resolver" / "resources" / "plugInfo.json",
        "plugInfo.json"
    )
    check_file(
        Path(omni_root) / "omni_client_library" / "omniclient.dll",
        "omniclient.dll"
    )
else:
    results.append((FAIL, "Cannot check files — OMNI_ROOT not set"))

# --- PATH coverage ---
path_val = os.environ.get("PATH", "")
for fragment in ["omni_usd_resolver", "omni_client_library"]:
    if fragment.lower() in path_val.lower():
        results.append((PASS, f"PATH contains '{fragment}'"))
    else:
        results.append((FAIL, f"PATH does not contain '{fragment}' — DLL load will fail"))

# --- Print results ---
print("\n=== Environment Check ===")
any_fail = False
for status, msg in results:
    if status:
        print(f"[{status}] {msg}")
    else:
        print(msg)
    if status == FAIL:
        any_fail = True

print()
if any_fail:
    print("RESULT: FAIL — fix the above before running resolver tests")
else:
    print("RESULT: PASS — environment looks correct")

quit()
