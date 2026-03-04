# USD Resolver (`omni_usd_resolver.dll`)

**Repo:** `usd-resolver`
**Build output:** `_build/windows-x86_64/release/omni_usd_resolver.dll`

USD reference: [Asset Resolution (Ar)](https://openusd.org/release/api/ar_page_front.html)

---

## What is a USD Resolver?

USD (Universal Scene Description) treats all asset paths — file paths, URLs, database IDs — as
opaque strings that must be *resolved* into concrete data. The **Asset Resolution** (`Ar`) library
is responsible for this translation. It provides a pluggable interface so studios can back USD
assets with any storage system: local filesystem, network volumes, cloud object stores, or a
proprietary asset management system like NVIDIA Nucleus.

### The resolver singleton

All resolution goes through a single entry point:

```cpp
ArResolver& resolver = ArGetResolver();
```

This returns a **singleton** object that internally dispatches to the appropriate implementation
based on the asset path. Clients never instantiate resolver subclasses directly.

### Primary resolver vs URI resolvers

USD maintains two categories of resolver:

| Type | Handles | Elected by |
|------|---------|------------|
| **Primary resolver** | All paths with no scheme prefix (e.g. `/path/to/file.usd`, `./relative.usd`) | `ArSetPreferredResolver()` or automatic election |
| **URI resolver** | Paths with a specific scheme prefix (e.g. `http://`, `s3://`) | `uriSchemes` list in `plugInfo.json` |

`OmniUsdResolver` is registered as the **primary resolver**. It intercepts all path resolution
so that `omniverse://` paths are handled by the Omniverse client library, while non-Omniverse
paths fall through to `ArDefaultResolver` (filesystem). A resolver with `uriSchemes` in its
`plugInfo.json` is permanently disqualified from being primary (see Problem 9 below).

### Key virtual methods

`ArResolver` is a pure virtual base class. `OmniUsdResolver` must implement:

| Method | Purpose |
|--------|---------|
| `_CreateIdentifier()` | Normalise an asset path into a canonical identifier |
| `_CreateIdentifierForNewAsset()` | Canonical identifier for a path about to be written |
| `_Resolve()` | Convert an identifier to a `ArResolvedPath` (concrete location) |
| `_OpenAsset()` | Return an `ArAsset` object for reading |
| `_OpenAssetForWrite()` | Return an `ArWritableAsset` object for writing |
| `_GetModificationTimestamp()` | Return a timestamp for cache invalidation |

`OmniUsdResolver` also declares `implementsContexts: true` and `implementsScopedCaches: true`
in `plugInfo.json`, meaning it implements `_BindContext()` / `_UnbindContext()` for
`ArResolverContext` binding and `_BeginCacheScope()` / `_EndCacheScope()` for
`ArResolverScopedCache`.

### Resolver contexts

An `ArResolverContext` carries per-operation configuration (search paths, session tokens, etc.)
and is bound thread-locally using `ArResolverContextBinder`. Different USD stages can use
different contexts to resolve the same logical path to different physical locations.

### Scoped caches

`ArResolverScopedCache` ensures repeated calls to `Resolve()` for the same path return the
same result within a scope, avoiding redundant network lookups on Nucleus.

---

## Purpose of `OmniUsdResolver`

Implements the `ArResolver` interface so that `omniverse://` paths encountered anywhere in
Houdini's USD pipeline are handled by the Omniverse client library (`omniclient.dll`) rather
than the default filesystem resolver.

When USD encounters `omniverse://nucleus.server/assets/cube.usd`:
1. `ArGetResolver()` returns the `OmniUsdResolver` singleton (elected as primary via `ready.py`)
2. USD calls `OmniUsdResolver::_Resolve()` with the path
3. The resolver calls into `omniclient.dll` to resolve or fetch the asset from Nucleus
4. Houdini receives a local-cache path or stream that it can open as a USD layer

---

## Key Source Files

| File | Role |
|------|------|
| [source/library/OmniUsdResolver_Ar2.h](../../usd-resolver/source/library/OmniUsdResolver_Ar2.h) | Class declaration — `OMNIUSDRESOLVER_EXPORT_CPP` required for vtable export |
| [source/library/OmniUsdResolver_Ar2.cpp](../../usd-resolver/source/library/OmniUsdResolver_Ar2.cpp) | Registration, constructor, resolver method implementations |
| [source/library/plugInfo-windows.json](../../usd-resolver/source/library/plugInfo-windows.json) | USD plugin registry entry for Windows |
| [include/Defines.h](../../usd-resolver/include/Defines.h) | `OMNIUSDRESOLVER_EXPORT_CPP` macro (`__declspec(dllexport)` on Windows) |
| [premake5.lua](../../usd-resolver/premake5.lua) | Build configuration — libs, defines, paths |

---

## USD Plugin Registration Chain

For the resolver to be instantiated, four things must all succeed in order:

```
1. Plug registry reads plugInfo.json (via HOUDINI_USD_DSO_PATH)
         ↓
2. TfType::Define<OmniUsdResolver>() registers the type + base class relationship
         ↓
3. SetFactory<Ar_ResolverFactory<OmniUsdResolver>>() stores the factory
         ↓
4. ready.py: ArSetPreferredResolver("OmniUsdResolver")
         ↓
5. ArGetResolver() → factory->New() → OmniUsdResolver singleton created
```

Steps 2 and 3 are normally triggered by the `AR_DEFINE_RESOLVER` macro, which expands to
`TF_REGISTRY_FUNCTION(TfType)`. In our build, the `.pxrctor` PE section mechanism that macro
relies on does not emit entries, so a standard C++ static initialiser (`_ResolverRegistration`)
performs the same `TfType::Define<>().SetFactory<>()` call instead (see issue #3 below).

---

## Windows DLL Boundary Issues

These are the non-obvious Windows-specific problems encountered. Each is documented in full in
[development_history.md](../development_history.md).

### 1. Virtual method export — class-level `__declspec(dllexport)` required

The class declaration must carry `OMNIUSDRESOLVER_EXPORT_CPP`:

```cpp
class OMNIUSDRESOLVER_EXPORT_CPP OmniUsdResolver final : public PXR_NS::ArResolver
```

Method-level decoration alone is insufficient. Without class-level decoration the vtable is not
exported and virtual dispatch silently fails even though TfType registers and the DLL loads.

### 2. `dynamic_cast` across DLL boundaries — `type_info` mismatch

`TfType::GetFactory<Ar_ResolverFactoryBase>()` internally calls
`dynamic_cast<Ar_ResolverFactoryBase*>`. On Windows, `type_info` identity is per-DLL unless
the class vtable is explicitly imported. `Ar_ResolverFactoryBase` has `AR_API` only on
individual methods (not the class declaration), so each DLL compiles its own local vtable and
`type_info`. The cast compares pointers from different DLLs and silently returns null.

Fix — force import of `Ar_ResolverFactoryBase` vtable/type_info from `libpxr_ar.dll`.
`Ar_ResolverFactory<T>` is a header-only template and must be instantiated locally;
`Ar_ResolverFactoryBase` has `AR_API` so its identity comes from `libpxr_ar.dll` automatically.
A linker `/INCLUDE` directive pulls in the destructor symbol which drags the vtable along:

```cpp
#pragma comment(linker, \
  "/INCLUDE:??1Ar_ResolverFactoryBase@pxrInternal_v0_25_5__pxrReserved__@@UEAA@XZ")
```

### 3. `MFB_ALT_PACKAGE_NAME` missing — `.pxrctor` section never emitted

`TF_REGISTRY_FUNCTION` expands to `ARCH_CONSTRUCTOR`, which uses
`__declspec(allocate(".pxrctor"))` to place a function pointer in a custom PE section.
`Arch_ConstructorInit` (from `libpxr_arch.dll`) scans this section at DLL load and invokes
all registered functions — this is what calls `SetFactory` and completes step 3 above.

If `MFB_ALT_PACKAGE_NAME` is undefined, `ARCH_CONSTRUCTOR` compiles without error but
produces no `.pxrctor` entry. The factory is never registered and `ArGetResolver()` falls
back to `ArDefaultResolver`.

Required defines in `premake5.lua`:

```lua
filter { "system:windows" }
    defines {
        "ARCH_OS_WINDOWS",
        "MFB_ALT_PACKAGE_NAME=omni_usd_resolver"
    }
filter{}
```

**Current status:** Resolved — factory registered in `_ResolverRegistration` (standard C++ static
initialiser) instead of relying on `.pxrctor`. Both required defines are present in `premake5.lua`.
See [debugging.md](debugging.md) for full history.

### 4. `uriSchemes` in `plugInfo.json` disqualifies primary resolver

USD's `resolver.cpp` sets `canBePrimaryResolver = info.uriSchemes.empty()`. Any resolver
that declares `uriSchemes` is permanently reclassified as a URI resolver and cannot be
elected as primary — `ArSetPreferredResolver` will have no effect on it.

The key must be absent from `plugInfo-windows.json`. The current file correctly omits it:
```json
"OmniUsdResolver": {
    "bases": [ "ArResolver" ],
    "implementsContexts": true,
    "implementsScopedCaches": true
}
```

---

## Plugin Discovery

USD's `Plug` library scans directories listed in `HOUDINI_USD_DSO_PATH` for `plugInfo.json`
files. The launcher sets:

```bat
set HOUDINI_USD_DSO_PATH=%OMNI_ROOT%\omni_usd_resolver\usd\omniverse\resolver\resources
```

The `plugInfo.json` at that path names the DLL (`LibraryPath`) and the resolver type.

---

## Linking Requirements (Windows)

All three must be linked or the TfType/factory registry is siloed from Houdini's process-wide
registry:

| Library | Why |
|---------|-----|
| `libpxr_ar.lib` | Shared `TfType` and `Ar_ResolverFactoryBase` ABI with Houdini |
| `libpxr_boost.lib` | USD 25.05 internalised pxr_boost (replaces external boost) |
| `libpxr_python.lib` | USD 25.05 internalised pxr_python |

All located in: `C:/Program Files/Side Effects Software/Houdini 21.0.631/custom/houdini/dsolib/`

---

## ABI / Namespace Requirement

The resolver DLL **must** be compiled against Houdini 21's exact USD 25.05 headers. The C++
namespace `pxrInternal_v0_25_5__pxrReserved__` is baked into every mangled symbol. A DLL
built against USD 24.x or even USD 25.02 will load but all vtable calls and type registrations
silently fail because the mangled names do not match.

```bat
:: Verify correct namespace in exports
dumpbin /exports omni_usd_resolver.dll | findstr /i "OmniUsdResolver"
```

All exported symbols should contain `pxrInternal_v0_25_5`.
