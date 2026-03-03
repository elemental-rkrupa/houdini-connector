# Houdini Connector Components

**Repo:** `houdini-connector`

The connector is the outer integration layer that Houdini loads at startup. It registers Omniverse
as a file system provider, adds UI panels for Nucleus connection management, and ensures the
`omni_usd_resolver.dll` is available to USD's plugin system.

---

## C++ Plugins (DSO)

These are compiled DLLs that Houdini loads from the `houdini/dso/` directory in the staging folder.

### `FS_Omni.dll`

**Source:** [FS_Omni/](../../houdini-connector/FS_Omni/)

Registers Houdini as a filesystem handler for `omniverse://` URLs. When a user types or navigates
to an `omniverse://` path in any Houdini file browser, this DLL intercepts the request.

| File | Role |
|------|------|
| `FS_Omni.h/.cpp` | Core filesystem handler registration |
| `FS_OmniReadHelper.h/.cpp` | Stat, directory listing, file open via Omniverse client |
| `FS_OmniWriteHelper.h/.cpp` | File create, delete, rename via Omniverse client |
| `FS_OmniInfoHelper.h/.cpp` | Path and metadata utilities |

**Houdini 21 change (Problem 1):** `FS_WriterStream` constructor API changed. The `const char*`
cache-path constructor was removed. Must now use default constructor + `init()`:

```cpp
// Before (Houdini 20.5):
FS_OmniWriterStream(...) : FS_WriterStream(cachePath) {}

// After (Houdini 21):
FS_OmniWriterStream(...) : FS_WriterStream() { init(cachePath); }
```

Required headers that were also missing: `<FS/FS_WriterStream.h>`, `<UT/UT_DirUtil.h>`,
`<fstream>`, `<iostream>`.

**Startup hang (Problem 5):** On launch, `FS_Omni.dll` reads `HOMNI_DEFAULT_CONNECTIONS`
and attempts TCP connections to those Nucleus servers. If the server is unreachable, the UI
thread deadlocks. Fix: clear the variable in the launcher — users connect explicitly via the
Omniverse panel.

### `OP_Omni.dll`

**Source:** [OP_Omni/](../../houdini-connector/OP_Omni/)

Provides Houdini operators (nodes) for Omniverse workflows — LOP live sync, custom commands, etc.

| File | Role |
|------|------|
| `CMD_Omni.cpp` | Custom Houdini hscript command implementations |
| `LOP_OmniLiveSync.h/.cpp` | LOP (USD stage) live sync operator |

**Houdini 21 linker fix (Problem 2):** USD 25.05 internalised boost. Two new libs required:
- `libpxr_python.lib`
- `libpxr_boost.lib`

Both from `C:\Program Files\Side Effects Software\Houdini 21.0.631\custom\houdini\dsolib\`.

### `HoudiniOmni` (library)

**Source:** [HoudiniOmni/](../../houdini-connector/HoudiniOmni/)

Shared library used by both `FS_Omni` and `OP_Omni`. Wraps the Omniverse client library
(`omniclient.dll`) and provides session management, asset info, and connection state.

---

## Python Layer

### `homni` module

**Source:** [python/python_libs/homni/](../../houdini-connector/python/python_libs/homni/)
**Deployed to:** `_staging/houdini21.0/houdini/python3.11libs/homni/`

Python utilities for the UI panels and scripts. Includes logging, helpers, dialogs, and panel
definitions.

**Houdini 21 change (Problem 4):** All imports must use `PySide6` not `PySide2`. Houdini 21
dropped PySide2. Fix must be applied to source `.py` files — staging is regenerated on each build.

```python
# Before:
from PySide2.QtWidgets import ...

# After:
from PySide6.QtWidgets import ...
```

### `HoudiniOmniPy` (Python bindings)

**Source:** [HoudiniOmniPy/](../../houdini-connector/HoudiniOmniPy/)

Compiled Python extension module exposing the `HoudiniOmni` C++ library to Python.

---

## Startup Scripts

Houdini runs Python scripts at different points during startup. The execution order is:

| Script | When | Modes |
|--------|------|-------|
| `pythonrc.py` | Very early — before UI, before HDAs load | All |
| `ready.py` | After all HDAs load, before any scene | All (including hython) |
| `uiready.py` | After UI is fully ready | Interactive only |
| `123.py` | When Houdini starts with no scene file | Interactive only |
| `456.py` | On every scene load / File > New | Interactive only |

See: [SideFX docs — Python script locations](https://www.sidefx.com/docs/houdini/hom/locations.html)

### `ready.py` — Preferred Resolver Election

**Deployed to:** `_staging/houdini21.0/houdini/python3.11libs/ready.py`

```python
from pxr import Ar
print("ready.py: Setting preferred resolver")
Ar.SetPreferredResolver("OmniUsdResolver")
Ar.GetResolver()
```

Runs after HDAs are loaded in **all modes including hython**, making it the correct place to
elect and instantiate the resolver. `Ar.GetResolver()` is called immediately to eagerly
instantiate the singleton — by the time any scene loads or any test script runs, the resolver
type is already fixed.

`ready.py` was chosen over `456.py` because:
- It runs before any scene file is opened (resolver ready for the first load)
- It runs in hython sessions (essential for automated testing)
- It runs once at startup rather than on every scene load

### `456.py`

**Deployed to:** `_staging/houdini21.0/houdini/scripts/456.py`

Runs on every scene load and after `File > New`. Previously contained the
`ArSetPreferredResolver` call — this was moved to `ready.py`. `456.py` does not run in
hython sessions, making it unsuitable for resolver initialisation.

### `pythonrc.py`

Executes very early, before HDAs load. Initialises the Omniverse Python environment.

---

## UI Panels and Shelf Tools

### `Omniverse.pypanel`

**Path:** `assets/python_panels/Omniverse.pypanel`

The main Omniverse connection management panel, embedded in Houdini's pane tab system. Allows
users to connect to Nucleus servers, browse assets, and manage sessions.

### `AssetValidator.pypanel`

Asset validation UI, accessible from the Omniverse panel.

### `omni.shelf`

**Path:** `assets/toolbar/omni.shelf`

Houdini shelf with Omniverse-specific tool buttons.

---

## USD Output Plugins (`husdplugins`)

**Path:** `assets/husdplugins/`

Python plugins that hook into Houdini's USD export (HUSD) pipeline:

| Plugin | Purpose |
|--------|---------|
| `omnicheckpoints.py` | Write USD checkpoints (versions) on Nucleus |
| `omnimdlproperties.py` | Export MDL material properties |
| `omnisimplerelativepaths.py` | Rewrite paths to relative form |
| `omnitextureexport.py` | Export and re-link textures |
| `omniusdformat.py` | Set USD output format preferences |

---

## Houdini Digital Assets (HDAs)

**Path:** `assets/otls/`

`.hda` files providing Omniverse-specific Houdini nodes. Includes MDL material operators
(`mdl_omni*.hda`), Omniverse utility SOPs (`sop_omni_*.hda`), and generic Omniverse nodes
(`omni_*.hda`). Legacy variants exist in `assets19.0/` and `assets19.5/`.

---

## Runtime Dependencies in Staging

The `omni/` folder in staging carries the Omniverse SDK DLLs that the connector DLLs depend on:

| Folder | Contents |
|--------|---------|
| `omni/omni_client_library/` | `omniclient.dll` + Python bindings — Nucleus communication |
| `omni/carb_sdk_plugins/` | Carbonite framework plugins — logging, settings, task system |
| `omni/omni_usd_resolver/` | `omni_usd_resolver.dll` + `plugInfo.json` |
