# Development History: Houdini 21 Omniverse Connector

## Overarching Purpose

The goal of this project is to port the **NVIDIA Omniverse Connector for Houdini** from Houdini 20.5 to **Houdini 21**, restoring the ability for end artists at studios to:

- Browse and open USD assets stored on a **cloud-based NVIDIA Nucleus server** directly from Houdini's native file browsers
- Load and resolve `omniverse://` USD asset paths transparently within Houdini's USD pipeline
- Manage Nucleus connections via UI panels integrated into Houdini

NVIDIA shipped a working, pre-built connector for Houdini versions up to 20.5. They have **not released an official build for Houdini 21** and have indicated no plans to do so. However, NVIDIA has made the source code for both the connector and an older version of the resolver publicly available on GitHub. This project forks those repos and adapts them for Houdini 21.

The connector is **not a developer tool** — it is used by production artists. It needs to work silently and correctly without manual intervention. A broken or missing USD resolver means `omniverse://` paths fail to load, which is a hard blocker for studio workflows that depend on Nucleus for asset storage.

---

## Architecture Overview

The connector consists of two separate repositories that work together:

### `houdini-connector`
The outer integration layer deployed into Houdini. Contains:
- **Staging structure** (`_staging/houdini21.0/`) — the folder tree deployed to artists
- **`houdini.env`** — environment variables Houdini loads at startup (plugin paths, debug flags)
- **`plugInfo.json`** — USD plugin registry metadata that tells USD where to find the resolver
- **Startup scripts** (`houdini/scripts/456.py`) — Python executed by Houdini on scene load
- **Omniverse client DLLs** (`omni_client_library`) — NVIDIA's Nucleus communication layer
- **UI panels and shelf tools** — connection management, Nucleus browser integration into Houdini's file dialogs
- **`omni_usd_resolver.dll`** — the compiled resolver DLL, copied here from the `usd-resolver` build output

The connector needed **more adaptation than the resolver** when moving to Houdini 21 — the staging structure, environment configuration, and UI integration all required significant updates beyond just swapping the resolver DLL.

### `usd-resolver`
The C++ plugin that implements USD's `ArResolver` interface, compiled into `omni_usd_resolver.dll`. This DLL:
- Registers itself with USD's plugin system via `plugInfo.json`
- Intercepts `omniverse://` path resolution requests from USD
- Uses the Omniverse client library (`omniclient.dll`) to communicate with the Nucleus server
- Must be compiled specifically against the USD version that ships with the target Houdini version

The resolver DLL is built from the `usd-resolver` repo and **manually copied** into the `houdini-connector` staging folder. The two repos are separately maintained but tightly coupled — a resolver built against the wrong USD version will silently fail.

---

## Why the Port is Non-Trivial

### The USD Version Jump

Houdini 20.5 shipped with USD 24.x. Houdini 21 ships with **USD 25.05**, which uses a different internal C++ namespace:

| Houdini | USD Version | C++ Namespace |
|---------|-------------|---------------|
| 20.5 | 24.x | `pxrInternal_v0_24_x__pxrReserved__` |
| 21.0 | 25.05 | `pxrInternal_v0_25_5__pxrReserved__` |

Every mangled C++ symbol in every Houdini USD DLL changed. A resolver DLL compiled against USD 24.x cannot be loaded by Houdini 21 — all vtable lookups, factory registrations, and type casts will silently fail because the mangled names don't match. The resolver source NVIDIA published was built against USD 25.02 (namespace `v0_25_2`), which also does not match. It therefore needed to be recompiled against Houdini 21's exact USD 25.05 headers and libraries.

### Windows DLL Boundary Complexity

USD's plugin system relies on several mechanisms that behave differently across DLL boundaries on Windows compared to Linux/macOS. Several subtle failures in this area consumed the majority of debugging effort and are documented in detail below.

---

## Repository Setup

- **Base:** NVIDIA's public GitHub releases of `houdini-connector` and `usd-resolver`
- **Working forks:** Personal forks with commits tracking all changes in this document
- **Build target:** `windows-x86_64`, release configuration
- **Build command:**
  ```bat
  cd C:\Users\rober\Documents\GitHub\usd-resolver
  repo build --usd-flavor houdini --usd-ver 25.05 --python-ver 3.11
  ```
- **Build output:** `_build/windows-x86_64/release/omni_usd_resolver.dll`
- **Deploy target:** `houdini-connector/_staging/houdini21.0/omni/omni_usd_resolver/omni_usd_resolver.dll`

### Key Dependencies

| Dependency | Location | Purpose |
|------------|----------|---------|
| Houdini 21 USD headers | `C:/Program Files/Side Effects Software/Houdini 21.0.631/toolkit/include/` | Build against correct USD version |
| Houdini 21 import libs | `C:/Program Files/Side Effects Software/Houdini 21.0.631/custom/houdini/dsolib/` | Link against Houdini's USD DLLs |
| `usd-resolver-deps` | `C:/tmp/usd-resolver-deps/` | Pre-extracted USD headers matching Houdini 21 |
| Omniverse client library | `_build/target-deps/omni_client_library/` | Nucleus communication |
| Python 3.11 | `_build/usd-deps/python/` | Python bindings |

---

## Problem History & Discoveries

Each problem is documented in the order it was discovered. Many produce no useful error messages and would be very hard to diagnose without this context.

The work fell into two distinct phases:

- **Phase 1 — Building the `houdini-connector` for Houdini 21** (Problems 1–6): Getting the C++ plugin DLLs (`FS_Omni.dll`, `OP_Omni.dll`) to compile and the staging environment to deploy and launch correctly.
- **Phase 2 — Building and integrating a compatible `omni_usd_resolver.dll`** (Problems 7–13): Getting USD's `omniverse://` resolver to actually load and function under Houdini 21's USD 25.05 ABI.

---

## Phase 1: Building the houdini-connector for Houdini 21

---

### Problem 1 (Phase 1): `FS_WriterStream` — Base Class Undefined

**Symptom:** Build error: `'FS_WriterStream': base class undefined` in `FS_Omni/FS_OmniWriteHelper.cpp`, plus `'cerr': undeclared identifier`.

**Root cause:** Two separate issues in the same file:
1. `FS_WriterStream` was declared as a base class but the class definition was not visible — the header `FS_Writer.h` only forward-declares it. Without the full definition the subclass could not compile.
2. `cerr` was used without `#include <iostream>`. The file already had `using namespace std;` but the `<iostream>` include was missing.

Additionally, Houdini 21 changed the `FS_WriterStream` constructor API: the `const char*` constructor that accepted a cache path was removed. In Houdini 21, construction requires a default constructor followed by calling `init()`.

**Fix — `FS_Omni/FS_OmniWriteHelper.cpp`:**
1. Add the missing headers:
   ```cpp
   #include <FS/FS_WriterStream.h>
   #include <UT/UT_DirUtil.h>
   #include <fstream>
   #include <iostream>
   ```
2. Change the constructor of the inner `FS_OmniWriterStream` class from:
   ```cpp
   FS_OmniWriterStream(const string& omniPath, const char* cachePath)
       : FS_WriterStream(cachePath), m_omniPath(omniPath) {}
   ```
   to:
   ```cpp
   FS_OmniWriterStream(const string& omniPath, const char* cachePath)
       : FS_WriterStream(), m_omniPath(omniPath)
   {
       init(cachePath);
   }
   ```

**Result:** `FS_Omni.dll` compiled successfully.

---

### Problem 2 (Phase 1): Unresolved Externals — `pxr_boost::python` Symbols

**Symptom:** Linker errors in `OP_Omni`: unresolved external symbols in the namespace `pxrInternal_v0_25_5__pxrReserved__::pxr_boost::python`.

**Root cause:** Two compounding issues:

1. **USD 25.05 internalised boost.** OpenUSD removed its external `boost` dependency. `pxr_boost::python` symbols now live in Houdini 21's own `libpxr_python.lib` and `libpxr_boost.lib`, not in the old `hboost_python311-mt-x64.lib`. The `OP_Omni/CMakeLists.txt` was not linking against these new libraries.

2. **Wrong files in `houdini_usd/lib`.** The `C:\tmp\omniverse-connector\houdini_usd\lib` staging folder had been populated with the Python USD package directories (e.g. `lib/pxr/Usd/`, `lib/pxr/Sdf/`) rather than `.lib` import libraries. These are completely different things — one is for Python, the other is for the C++ linker.

**Fix:**
1. Cleared and re-populated `houdini_usd/lib` with the actual `.lib` files from Houdini 21's install:
   ```bat
   rmdir /s /q "C:\tmp\omniverse-connector\houdini_usd\lib"
   mkdir "C:\tmp\omniverse-connector\houdini_usd\lib"
   xcopy /I "C:\Program Files\Side Effects Software\Houdini 21.0.631\custom\houdini\dsolib\*.lib" "C:\tmp\omniverse-connector\houdini_usd\lib"
   ```
2. Added the two new libs to `OP_Omni/CMakeLists.txt`'s `target_link_libraries` (Windows section):
   ```cmake
   ${HOUDINI_DIR}/custom/houdini/dsolib/libpxr_python.lib
   ${HOUDINI_DIR}/custom/houdini/dsolib/libpxr_boost.lib
   ```
   These are in addition to the pre-existing `hboost_python311-mt-x64.lib` (which still provides other boost symbols).

**Note:** `${HOUDINI_DIR}` resolves to `C:\tmp\omniverse-connector\houdini_hdk`, so the libs needed to be present there as well. They were copied from the `houdini_usd/lib` staging folder.

**Result:** `OP_Omni.dll` linked successfully. Both DLLs built.

---

### Problem 3 (Phase 1): Staging Folder Named `houdini20.5` Instead of `houdini21.0`

**Symptom:** After a successful build, the staging folder was named `_staging/houdini20.5/` instead of `_staging/houdini21.0/`. The launcher `houdini_launcher.bat --hver 21.0.631` therefore pointed at a nonexistent path.

**Root cause:** `parse_args.bat` contained version-specific `if/else` blocks for each Houdini version but had no block for Houdini 21.0. The default fallback was Houdini 20.5. No error was raised — it silently used the wrong version.

**Fix — `parse_args.bat`:** Added a new `else if` block and changed the default:
```bat
:init
    set "HOUDINI_FULL_VER=21.0.631"   <- was 20.5.332
    ...

    ) else if %HOUDINI_VER% == 21.0 (
        set "PY_VER=3.11"
        set "PY_VER_INT=311"
        set "EXCLUDED_PY_VERS=*cp37* *cp38* *cp39* *cp310* ..."
        set "HDK_PACKAGE_VER=21.0.631"
        set "USD_FLAVOR=houdini-24_03"
    )
```

**Note on `USD_FLAVOR`:** `houdini-25_05` was attempted first but no such packman package exists on NVIDIA's servers. `houdini-24_03` is used as the fallback — it is the last published flavor and is used only to satisfy the packman download step for the `omni_usd_resolver` binary. That binary is ultimately replaced by a locally-built version (see Phase 2).

**Result:** Staging folder correctly named `_staging/houdini21.0/`.

---

### Problem 4 (Phase 1): `ModuleNotFoundError: No module named 'PySide2'`

**Symptom:** On Houdini startup:
```
Error running pythonrc.py:
ModuleNotFoundError: No module named 'PySide2'
```
Plugin UI panels failed to initialise.

**Root cause:** Houdini 21 switched from **PySide2 to PySide6**. All Python source files in the connector still imported from `PySide2`.

**Fix:** Replace all `PySide2` imports with `PySide6` in all Python files under `houdini/python3.11libs/`. Then delete all `.pyc` bytecode caches and `__pycache__` directories, which retain old compiled bytecode even after the source files are updated:
```bat
del /s /q "_staging\houdini21.0\houdini\python3.11libs\*.pyc"
for /d /r "_staging\houdini21.0" %d in (__pycache__) do @if exist "%d" rd /s /q "%d"
```

**Important:** The staging folder is regenerated on every build. The fix must be applied to the source `.py` files in the repo, not just the staging copies. Files to update can be found with:
```bat
findstr /s /i "PySide2" "C:\Users\rober\Documents\GitHub\houdini-connector\*.py"
```

**Result:** Houdini launched without Python errors. Plugin UI panels visible.

---

### Problem 5 (Phase 1): Standard File Browser Hangs on Open

**Symptom:** Opening Houdini's File → Open dialog caused the application to hang immediately and become unresponsive. This occurred regardless of whether any Omniverse path was being navigated.

**Diagnosis:** Isolated by temporarily renaming DLLs in `_staging/houdini21.0/houdini/dso/`:
- With `FS_Omni.dll` renamed to `.bak` → file browser opened normally.
- With `OP_Omni.dll` renamed to `.bak` → file browser opened normally.
- Root cause confirmed as `FS_Omni.dll`.

**Root cause:** `FS_Omni.dll` registers itself as a Houdini filesystem handler for `omniverse://` paths. On file browser initialisation, Houdini calls the handler, which reads `HOMNI_DEFAULT_CONNECTIONS` and calls into the Omniverse client library to establish connections to those servers. The launcher had `set HOMNI_DEFAULT_CONNECTIONS=localhost`. The client library blocked synchronously waiting for a TCP response from a Nucleus server that was not reachable at that address, deadlocking the UI thread.

**Fix — `houdini_launcher.bat`:** Clear the default connections so no connection attempt is made on startup:
```bat
set HOMNI_DEFAULT_CONNECTIONS=
```
Users connect to their Nucleus server explicitly via the Omniverse connection panel in the UI.

**Also fixed in the same commit:** Added `%HOUDINI_BIN%` to the launcher PATH:
```bat
set PATH=%OMNI_ROOT%\lib;%OMNI_ROOT%\omni_usd_resolver;%OMNI_ROOT%\omni_client_library;%HOUDINI_BIN%;%PATH%
```
This ensures Houdini's `libpxr_*.dll` files are findable by any DLL that depends on them at load time.

**Result:** File browser opens without hanging.

---

### Problem 6 (Phase 1): `omni_usd_resolver.dll` Fails to Load — ABI Incompatibility

**Symptom:** After the file browser fix, opening any `omniverse://` USD path failed:
```
Failed to open layer @omniverse://nucleus.eg/.../cube.geom.usd@
```
From Houdini's Python console:
```python
from pxr import Plug
reg = Plug.Registry()
# Omniverse USD Plugin  isLoaded = False
```
USD log output:
```
Failed to load plugin 'Omniverse USD Plugin': The specified module could not be found.
in 'omni_usd_resolver.dll'
```

**Investigation steps:**
- `dumpbin /dependents omni_usd_resolver.dll` showed dependencies on `libpxr_ar.dll`, `libpxr_arch.dll`, `libpxr_tf.dll`, `libpxr_trace.dll`, `libpxr_vt.dll`, `hboost_python311-mt-x64.dll`, `omniclient.dll`, `carb.dll`, `python311.dll`.
- All these DLLs were confirmed present in either the staging folder or Houdini's `bin/`. "The specified module could not be found" on Windows means a transitive dependency cannot be located at load time.
- Even after adding `%HOUDINI_BIN%` to PATH (fixing the load-time search), the resolver still reported `isLoaded = False`.
- Root cause confirmed: the `omni_usd_resolver.dll` in the staging folder was the **Houdini 20.5 build** (compiled against USD 24.03, namespace `pxrInternal_v0_24_x`). Houdini 21 uses USD 25.05 (namespace `pxrInternal_v0_25_5`). Every mangled C++ symbol differs. The DLL loads but all vtable calls and type registrations silently fail.

**Alternatives investigated before deciding to build from source:**
- **Gemini in-house tool** (`C:\Norrland\Gemini\tools\omni_usd_resolver.dll`): depends on `python312.dll` and monolithic USD names (`usd_usd.dll`, `usd_sdf.dll`) — incompatible with Houdini 21's Python 3.11 and `libpxr_*` naming.
- **Packman registry query:** `omnipackages.nvidia.com` was blocked by the network firewall; no registry browse was possible.
- **Local packman cache:** Only `omni_usd_resolver.houdini-24_03.py311` (20.5 era) and `omni.usd_resolver-1.0.0+...cp312` (Python 3.12) present — neither compatible.

**Conclusion:** No pre-built `omni_usd_resolver` compatible with Houdini 21 + Python 3.11 + USD 25.05 exists. The source code is public at https://github.com/NVIDIA-Omniverse/usd-resolver and must be compiled from source. This is the work documented in Phase 2.

---

## Phase 2: Building and Integrating a Compatible `omni_usd_resolver.dll`

---

### Problem 7 (Phase 2): "Failed to manufacture OmniUsdResolver"

**Symptom:** USD logs: `Failed to manufacture asset resolver OmniUsdResolver from plugin`.

**Root cause:** `libpxr_ar.lib` was missing from the linker inputs. Without it, USD's TfType registry was isolated — our DLL's type registrations were invisible to the factory lookup in Houdini's `libpxr_ar.dll`.

**Fix — `premake5.lua`:**
```lua
filter { "system:windows" }
    libdirs { "C:/Program Files/Side Effects Software/Houdini 21.0.631/custom/houdini/dsolib" }
    links { "libpxr_boost", "libpxr_python", "libpxr_ar" }
filter {}
```

---

### Problem 8 (Phase 2): Virtual Methods Not Exported from DLL

**Symptom:** Built DLL only exported 6 functions (non-virtual utilities). None of the `ArResolver` virtual methods (`_Resolve`, `_CreateIdentifier`, `_OpenAsset`, etc.) were exported.

**Root cause:** On Windows, `__declspec(dllexport)` must be applied to the **class declaration** to export the vtable and all virtual methods. Decorating individual methods is insufficient for a polymorphic class.

**Fix — `OmniUsdResolver_Ar2.h`:**
```cpp
#include "../../include/Defines.h"
class OMNIUSDRESOLVER_EXPORT_CPP OmniUsdResolver final : public PXR_NS::ArResolver
```

Where `OMNIUSDRESOLVER_EXPORT_CPP` expands to `__declspec(dllexport)` on Windows (defined in `include/Defines.h`).

**Result:** DLL grew to 170,496 bytes with 30 exported symbols, all correctly in the `pxrInternal_v0_25_5__pxrReserved__` namespace.

---

### Problem 9 (Phase 2): `uriSchemes` in `plugInfo.json` Blocking Primary Resolver

**Symptom:** `OmniUsdResolver` registered but only elected as a URI resolver, not the primary resolver. `ArDefaultResolver` handled all paths.

**Root cause:** In USD's `resolver.cpp`, `canBePrimaryResolver = info.uriSchemes.empty()`. Any resolver with `uriSchemes` defined is permanently disqualified from being primary.

**Fix — `plugInfo.json`:** Remove the `uriSchemes` key entirely.

---

### Problem 10 (Phase 2): `ArSetPreferredResolver` Timing — A Red Herring

It was initially suspected that `456.py` (which calls `ArSetPreferredResolver("OmniUsdResolver")`) was running too late. The AR_RESOLVER_INIT debug output disproved this:
```
ArGetResolver(): Using preferred resolver OmniUsdResolver
```
The call was always in time. The failure was downstream in `factory->New()`. **Do not spend time trying to move this call earlier** — it is not the problem.

---

### Problem 11 (Phase 2): Constructor Never Called — SEH Debugging Complication

**Symptom:** USD selected `OmniUsdResolver` as preferred but fell back to `ArDefaultResolver`. Constructor `fprintf` never printed.

**Complication:** Attempting to use Windows SEH (`__try/__except`) to catch the failure produced MSVC error C2712: `Cannot use __try in functions that require object unwinding`. SEH cannot coexist with C++ RAII objects in the same function.

**Fix for debugging:** Moved SEH code to a new `.c` file (`DebugTest.c`). C translation units have no C++ unwinding, so `__try` compiles. Called from `.cpp` via `extern "C"`.

**Discovery:** Direct instantiation via `new OmniUsdResolver()` succeeded. The constructor itself was fine. The failure was inside USD's `factory->New()` call in `_PluginResolver::Create()`.

---

### Problem 12 (Phase 2): Factory Returns Null — `type_info` Mismatch Across DLL Boundaries

**Symptom:** `TfType::GetFactory<Ar_ResolverFactoryBase>()` returned null despite the factory having been registered.

**Root cause:** `TfType::GetFactory<T>()` is implemented as:
```cpp
template <class T>
T* GetFactory() const { return dynamic_cast<T*>(_GetFactory()); }
```

On Windows, `dynamic_cast` works by comparing `type_info` pointers, and `type_info` identity is tied to a class's vtable. `Ar_ResolverFactoryBase` is declared in `defineResolver.h` with `AR_API` only on its destructor and `New()` method — **not on the class declaration itself**. This means each DLL compiles its own local copy of the vtable and `type_info`. When Houdini's `libpxr_ar.dll` performs the cast using its `type_info` and our DLL registered the factory using ours, the pointers differ and the cast silently returns null.

**Fix — `OmniUsdResolver_Ar2.cpp`:**
```cpp
// Force use of Houdini's vtable/type_info for Ar_ResolverFactoryBase
// so dynamic_cast<Ar_ResolverFactoryBase*> works across the DLL boundary
template class __declspec(dllimport) Ar_ResolverFactory<OmniUsdResolver>;

#pragma comment(linker, \
  "/INCLUDE:??1Ar_ResolverFactoryBase@pxrInternal_v0_25_5__pxrReserved__@@UEAA@XZ")
```

**Result:** Factory pointer became non-null.

---

### Problem 13 (Phase 2): `TF_REGISTRY_FUNCTION` Never Fires — Missing `.pxrctor` Section

**Symptom:** Print inside `TF_REGISTRY_FUNCTION` never appeared. DLL had no `.pxrctor` PE section. Factory was null when USD's `_CreateResolver` ran because `SetFactory` had never been called.

**Background — USD's registry mechanism on Windows:**

USD does not use standard CRT static initialisers for plugin registration. It uses a custom PE section:

1. `TF_REGISTRY_FUNCTION` expands via `TF_REGISTRY_DEFINE` to `ARCH_CONSTRUCTOR`
2. `ARCH_CONSTRUCTOR` on Windows uses `__declspec(allocate(".pxrctor"))` to place a function pointer in a custom `.pxrctor` PE section
3. `Arch_ConstructorInit` (imported from `libpxr_arch.dll`) scans the `.pxrctor` section at DLL load time and calls all registered functions
4. This calls `Tf_RegistryInit::Add(...)` which calls `SetFactory<Ar_ResolverFactory<OmniUsdResolver>>()`

**If `.pxrctor` is absent from the plugin DLL, the entire chain never runs and the factory is never registered.**

**Root cause:** `MFB_ALT_PACKAGE_NAME` was not defined in our build. This define is required by `Tf_RegistryStaticInit` and `Tf_RegistryInit::Add` for library identification. Without it, `ARCH_CONSTRUCTOR` silently produces broken code with no compile error and no `.pxrctor` section.

**Fix — `premake5.lua`:**
```lua
filter { "system:windows" }
    defines {
        "ARCH_OS_WINDOWS",
        "MFB_ALT_PACKAGE_NAME=omni_usd_resolver"
    }
filter{}
```

Note: `ARCH_OS_WINDOWS` auto-defines from `_WIN32` and is technically redundant, but `MFB_ALT_PACKAGE_NAME` is the essential missing define.

**Status at end of session:** Both defines confirmed present in the generated `.vcxproj`. The `.pxrctor` section is still absent from the rebuilt DLL. Investigation ongoing — see Recommended Next Steps.

---

## Summary of All File Changes

### `usd-resolver/premake5.lua`

| Change | Reason |
|--------|--------|
| Added `libpxr_ar.lib` to Windows linker | Shared TfType registry — without this, factory registrations are invisible to Houdini |
| Added `libpxr_boost`, `libpxr_python` to linker | Required by Houdini 21 USD 25.05 |
| Added Houdini `dsolib` to `libdirs` | Path to Houdini's `.lib` import files |
| Added `ARCH_OS_WINDOWS` define (Windows filter) | Belt-and-suspenders for `arch/attributes.h` Windows branch |
| Added `MFB_ALT_PACKAGE_NAME=omni_usd_resolver` define | Required for `ARCH_CONSTRUCTOR` / `TF_REGISTRY_FUNCTION` to emit `.pxrctor` section entries |

### `usd-resolver/source/library/OmniUsdResolver_Ar2.h`

| Change | Reason |
|--------|--------|
| Added `#include "../../include/Defines.h"` | Pull in `OMNIUSDRESOLVER_EXPORT_CPP` macro |
| Added `OMNIUSDRESOLVER_EXPORT_CPP` to class declaration | Export vtable and all virtual methods on Windows |

### `usd-resolver/source/library/OmniUsdResolver_Ar2.cpp`

| Change | Reason |
|--------|--------|
| `template class __declspec(dllimport) Ar_ResolverFactory<OmniUsdResolver>` | Force shared `type_info` for `Ar_ResolverFactoryBase` so `dynamic_cast` works across DLL boundary |
| `#pragma comment(linker, "/INCLUDE:...")` | Prevent linker from stripping the imported `Ar_ResolverFactoryBase` destructor symbol |
| Debug `fprintf` prints (temporary — remove before shipping) | Verify constructor, factory pointer, `TF_REGISTRY_FUNCTION` firing |

### `usd-resolver/source/library/DebugTest.c` (new file)

| Change | Reason |
|--------|--------|
| SEH wrapper `TryInstantiate()` in C (not C++) | MSVC C2712 prevents `__try/__except` in C++ functions with RAII objects; `.c` file sidesteps this |

### `houdini-connector/_staging/houdini21.0/houdini/scripts/456.py`

| Change | Reason |
|--------|--------|
| `ArSetPreferredResolver("OmniUsdResolver")` | Elect our resolver as primary before USD creates the resolver singleton |

### `houdini-connector/_staging/houdini21.0/houdini.env`

| Change | Reason |
|--------|--------|
| `TF_DEBUG = AR_RESOLVER_INIT PLUG_LOAD PLUG_INFO_SEARCH` | Essential verbose output for diagnosing resolver init failures |
| `PXR_PLUGINPATH_NAME` entry | Tell USD plug registry where to find our `plugInfo.json` |

### `houdini-connector/.../plugInfo.json`

| Change | Reason |
|--------|--------|
| Removed `uriSchemes` key | Its presence permanently disqualifies the resolver from being elected as primary |

---

## Non-Obvious / Unintuitive Findings

1. **`uriSchemes` in `plugInfo.json` permanently disqualifies a resolver from being primary.** `canBePrimaryResolver = info.uriSchemes.empty()` in USD's `resolver.cpp`. This is not documented anywhere obvious.

2. **Class-level `__declspec(dllexport)` is required for vtable export on Windows.** Method-level decoration alone is not sufficient. Without class-level decoration the DLL loads and TfType registers, but virtual dispatch silently fails.

3. **USD namespace must match exactly.** `v0_25_5` vs `v0_25_2` produces completely different mangled symbols. All failures are silent with no "wrong version" message.

4. **`ArSetPreferredResolver` runs in time — it is not the problem.** The AR_RESOLVER_INIT log confirms this. The actual failure is in factory registration, not timing.

5. **`dynamic_cast` across DLL boundaries silently returns null when `type_info` is per-DLL.** Classes with `AR_API` only on methods (not the class declaration) get a per-DLL vtable and `type_info`. `TfType::GetFactory` uses `dynamic_cast` internally and returns null. Fix: `template class __declspec(dllimport)` to force use of the host DLL's vtable.

6. **`MFB_ALT_PACKAGE_NAME` being undefined produces no error but silently breaks `TF_REGISTRY_FUNCTION`.** The macro compiles without complaint but produces no `.pxrctor` section entry. The factory is never registered. This is the hardest failure to diagnose in the entire chain.

7. **USD's `.pxrctor` mechanism is entirely separate from standard C++ static initialisers.** Standard `static` objects and CRT initialisers work fine (the `_DebugInit` struct runs correctly). `TF_REGISTRY_FUNCTION` uses a completely different PE section mechanism. One working tells you nothing about the other.

8. **`__try/__except` requires a separate `.c` file on MSVC.** MSVC C2712 prevents SEH in any function with C++ unwinding. Put SEH code in a `.c` file and call it via `extern "C"`.

9. **`repo build --rebuild` regenerates the project files, it does not do a MSBuild clean+rebuild.** Use `MSBuild.exe ... /t:Rebuild` for a build that skips premake and forces full recompilation.

10. **Check for `.pxrctor` in the `.obj` file, not just the final DLL.** Absence from the `.obj` means the problem is in macro expansion or missing defines — not the linker. This is the definitive early diagnostic.

---

## Current Status

The resolver DLL builds and loads correctly into Houdini 21. USD selects `OmniUsdResolver` as the preferred primary resolver. Direct constructor instantiation works.

**Outstanding blocker:** `TF_REGISTRY_FUNCTION` does not fire, meaning `SetFactory` is never called, and USD falls back to `ArDefaultResolver`. Both `MFB_ALT_PACKAGE_NAME` and `ARCH_OS_WINDOWS` are confirmed in the `.vcxproj` but `.pxrctor` remains absent from the `.obj` and final DLL.

### Recommended Next Steps

**Option A — Inspect preprocessed output to see exact macro expansion:**
```bat
cl /P /showIncludes /I<include paths> OmniUsdResolver_Ar2.cpp
```
Check for `#pragma section(".pxrctor", read)` and `__declspec(allocate(".pxrctor"))` in the output. Verify which `attributes.h` is actually being included.

**Option B — Bypass `TF_REGISTRY_FUNCTION` entirely (most likely to unblock quickly):**

The `_DebugInit` static initialiser is confirmed working. Register the factory from there:
```cpp
namespace {
struct _DebugInit {
    _DebugInit() {
        TfType::Define<OmniUsdResolver, TfType::Bases<ArResolver>>()
            .SetFactory<Ar_ResolverFactory<OmniUsdResolver>>();
        fprintf(stderr, "OmniUsdResolver factory registered\n");
        fflush(stderr);
    }
} _debugInit;
}
```
This uses a standard C++ static initialiser instead of the `.pxrctor` mechanism and sidesteps the entire unresolved issue.

**Option C — Inspect `arch/api.h`:**
Verify `ARCH_API` on `Arch_ConstructorInit` resolves to `__declspec(dllimport)` in our build context. Fetch `C:/tmp/usd-resolver-deps/usd/include/pxr/base/arch/api.h` and check the expansion.

---

## Build & Deploy Reference

```bat
:: Regenerate project (only when premake5.lua changes)
cd C:\Users\rober\Documents\GitHub\usd-resolver
repo build --usd-flavor houdini --usd-ver 25.05 --python-ver 3.11

:: Clean rebuild without regenerating
"C:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\MSBuild.exe" ^
  "C:\Users\rober\Documents\GitHub\usd-resolver\_compiler\vs2022\OmniUsdResolver.sln" ^
  /p:Configuration=release;Platform=x64 /t:Rebuild /verbosity:minimal

:: Deploy DLL to connector staging
copy /Y "C:\Users\rober\Documents\GitHub\usd-resolver\_build\windows-x86_64\release\omni_usd_resolver.dll" ^
  "C:\Users\rober\Documents\GitHub\houdini-connector\_staging\houdini21.0\omni\omni_usd_resolver\omni_usd_resolver.dll"
```

## Diagnostic Commands

```bat
:: PE sections — look for .pxrctor
dumpbin /headers omni_usd_resolver.dll

:: Check .pxrctor in obj file (diagnose macro expansion before linking)
dumpbin /headers _build\intermediate\windows\omni_usd_resolver\x86_64\release\OmniUsdResolver_Ar2.obj > obj.txt
findstr /i "pxrctor" obj.txt

:: Verify exports and USD namespace
dumpbin /exports omni_usd_resolver.dll | findstr /i "OmniUsdResolver"

:: Verify imports (libpxr_ar.dll, libpxr_arch.dll etc)
dumpbin /imports omni_usd_resolver.dll

:: Check Houdini's libpxr_ar.dll for Ar_ResolverFactoryBase exports
dumpbin /exports "C:\Program Files\Side Effects Software\Houdini 21.0.631\bin\libpxr_ar.dll" | findstr "Ar_ResolverFactoryBase"

:: Verify defines are in vcxproj
findstr /i "PreprocessorDefinitions" "_compiler\vs2022\omni_usd_resolver\omni_usd_resolver.vcxproj"
```

## Key USD Debug Log Lines

| Log line | What it means |
|----------|---------------|
| `Found primary asset resolver types: [OmniUsdResolver, ...]` | Plugin found, TfType registered correctly |
| `Using preferred resolver OmniUsdResolver` | `ArSetPreferredResolver` ran in time |
| `Loading plugin 'Omniverse USD Plugin'` | DLL being loaded by Plug |
| `Using default asset resolver ArDefaultResolver` | Factory manufacture failed — resolver fell back |
| `Found URI resolver OmniUsdResolver` | Registered as URI resolver (separate from primary resolver role) |
