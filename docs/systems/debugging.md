# Debugging & Diagnostics

---

## Status: RESOLVED

**Option B implemented — factory registered via standard C++ static initialiser.**

`TF_REGISTRY_FUNCTION` still does not fire (`.pxrctor` PE section absent from DLL), but the
factory is now registered in `_DebugInit::_DebugInit()` — a standard C++ static initialiser
that runs reliably at DLL load. `OmniUsdResolver` is elected as primary resolver and `omniverse://`
paths resolve correctly via Nucleus.

Confirmed working log sequence:
```
ready.py: Setting preferred resolver
ArGetResolver(): Using preferred resolver OmniUsdResolver
Loading plugin 'Omniverse USD Plugin'.
omni_usd_resolver.dll loaded
OmniUsdResolver factory registered via static init
Factory: 00000000D1D2A8B0
factory->New() returned: 00000000D163EA20
ArGetResolver(): Using asset resolver OmniUsdResolver ... for primary resolver
```

USD file loading from Nucleus (`omniverse://`) confirmed working in Houdini.

---

## Historical Blocker (resolved)

The `.pxrctor` PE section mechanism (`ARCH_CONSTRUCTOR` / `TF_REGISTRY_FUNCTION`) never emitted
entries in our build. Root cause unknown — both `MFB_ALT_PACKAGE_NAME` and `ARCH_OS_WINDOWS`
are confirmed in the `.vcxproj`. The Option B workaround (standard C++ static init) is the
permanent solution — it is simpler and equally correct.

---

## Recommended Next Steps (in priority order)

### Option A — Inspect preprocessed output

Verify what `arch/attributes.h` is actually doing with `ARCH_CONSTRUCTOR` in our build context:

```bat
cd C:\Users\rober\Documents\GitHub\usd-resolver\_compiler\vs2022

:: Run MSVC preprocessor on the source file
cl /P /showIncludes ^
  /I"C:/tmp/usd-resolver-deps/usd/include" ^
  /I"C:/Program Files/Side Effects Software/Houdini 21.0.631/toolkit/include" ^
  /DARCH_OS_WINDOWS /DMFB_ALT_PACKAGE_NAME=omni_usd_resolver ^
  "...\source\library\OmniUsdResolver_Ar2.cpp"
```

In the `.i` output file, search for:
- `#pragma section(".pxrctor"`
- `__declspec(allocate(".pxrctor"))`

If absent, the `ARCH_CONSTRUCTOR` macro is expanding incorrectly or the wrong `attributes.h`
is being included.

### Option B — Bypass `TF_REGISTRY_FUNCTION` with a standard static initialiser (fastest to unblock)

The `_DebugInit` static struct in `OmniUsdResolver_Ar2.cpp` is confirmed to run correctly.
Register the factory there instead of relying on `.pxrctor`:

```cpp
namespace {
struct _FactoryInit {
    _FactoryInit() {
        TfType::Define<OmniUsdResolver, TfType::Bases<ArResolver>>()
            .SetFactory<Ar_ResolverFactory<OmniUsdResolver>>();
        fprintf(stderr, "OmniUsdResolver factory registered via static init\n");
        fflush(stderr);
    }
} _factoryInit;
}
```

This sidesteps the entire `.pxrctor` mechanism. USD's `TF_REGISTRY_FUNCTION` is just
USD's preferred registration pattern — there is no functional requirement to use it.

### Option C — Inspect `arch/api.h`

Verify `ARCH_API` on `Arch_ConstructorInit` expands to `__declspec(dllimport)` in our context:

```bat
type "C:\tmp\usd-resolver-deps\usd\include\pxr\base\arch\api.h"
```

If `ARCH_API` resolves to `__declspec(dllexport)` (wrong direction), `Arch_ConstructorInit`
would be compiled locally rather than imported from `libpxr_arch.dll`, and the `.pxrctor`
scan would never run.

---

## Diagnostic Commands

### Check for `.pxrctor` section

```bat
:: In the final DLL
dumpbin /headers omni_usd_resolver.dll | findstr /i "pxrctor"

:: In the .obj (diagnose before linking)
dumpbin /headers ^
  "_build\intermediate\windows\omni_usd_resolver\x86_64\release\OmniUsdResolver_Ar2.obj" ^
  | findstr /i "pxrctor"
```

If absent from `.obj`, the problem is macro expansion or missing defines — not the linker.

### Check exports and USD namespace

```bat
dumpbin /exports omni_usd_resolver.dll | findstr /i "OmniUsdResolver"
```

Expected: symbols in `pxrInternal_v0_25_5__pxrReserved__` namespace, ~30 exported symbols.

### Check imports (DLL dependencies)

```bat
dumpbin /imports omni_usd_resolver.dll
```

Must include `libpxr_ar.dll`, `libpxr_arch.dll`, `libpxr_tf.dll`.

### Verify `Ar_ResolverFactoryBase` is exported from Houdini's `libpxr_ar.dll`

```bat
dumpbin /exports "C:\Program Files\Side Effects Software\Houdini 21.0.631\bin\libpxr_ar.dll" ^
  | findstr "Ar_ResolverFactoryBase"
```

### Verify defines in generated vcxproj

```bat
findstr /i "PreprocessorDefinitions" ^
  "_compiler\vs2022\omni_usd_resolver\omni_usd_resolver.vcxproj"
```

Must contain `ARCH_OS_WINDOWS` and `MFB_ALT_PACKAGE_NAME=omni_usd_resolver`.

### Check plugin load in Houdini

```python
from pxr import Plug
reg = Plug.Registry()
for p in reg.GetAllPlugins():
    if "omni" in p.name.lower():
        print(p.name, "isLoaded =", p.isLoaded)
```

---

## USD Debug Log Lines

Enable in `houdini.env`:
```
TF_DEBUG = AR_RESOLVER_INIT PLUG_LOAD PLUG_INFO_SEARCH
```

| Log line | Meaning |
|----------|---------|
| `Found primary asset resolver types: [OmniUsdResolver, ...]` | Plugin found, TfType registered |
| `Using preferred resolver OmniUsdResolver` | `ready.py` → `ArSetPreferredResolver` ran in time |
| `Loading plugin 'Omniverse USD Plugin'` | DLL being loaded by Plug |
| `Using default asset resolver ArDefaultResolver` | Factory manufacture failed — fallback |
| `Found URI resolver OmniUsdResolver` | Registered as URI-only resolver (wrong — `uriSchemes` present) |
| `Failed to manufacture asset resolver OmniUsdResolver` | `factory->New()` returned null |

---

## Non-Obvious Findings (reference)

1. **`uriSchemes` in `plugInfo.json` permanently disqualifies primary resolver.**
   `canBePrimaryResolver = info.uriSchemes.empty()` in USD's `resolver.cpp`. Remove the key entirely.

2. **Class-level `__declspec(dllexport)` required for vtable export.**
   Method-level decoration is insufficient. Without it the DLL loads but virtual dispatch fails.

3. **USD namespace must match exactly.**
   `v0_25_5` vs `v0_25_2` → completely different mangled symbols. All failures are silent.

4. **`ArSetPreferredResolver` timing is not the problem.**
   `AR_RESOLVER_INIT` log confirms `ready.py` runs in time. Factory registration is where it fails.

5. **`dynamic_cast` across DLL boundaries silently returns null when `type_info` is per-DLL.**
   Fix: `template class __declspec(dllimport) Ar_ResolverFactory<OmniUsdResolver>`.

6. **`MFB_ALT_PACKAGE_NAME` undefined → no compile error, no `.pxrctor` section.**
   The factory is never registered. Hardest failure to diagnose in the chain.

7. **USD `.pxrctor` mechanism is separate from standard C++ static initialisers.**
   Standard static objects work fine. `TF_REGISTRY_FUNCTION` uses a different PE section path.
   One working tells you nothing about the other.

8. **`__try/__except` requires a `.c` file on MSVC.**
   MSVC C2712: SEH cannot coexist with C++ RAII. Put SEH code in `DebugTest.c`, call via `extern "C"`.

9. **`repo build --rebuild` does not clean MSBuild.**
   Use `MSBuild.exe ... /t:Rebuild` to force full recompilation.

10. **Check `.pxrctor` in `.obj`, not just the DLL.**
    Absent from `.obj` → macro expansion problem. Absent from DLL but present in `.obj` → linker stripping.
