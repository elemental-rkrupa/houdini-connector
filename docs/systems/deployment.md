# Deployment & Staging

---

## Staging Folder

The build system assembles everything into a single folder that artists install:

```
houdini-connector/_staging/houdini21.0/
├── houdini/                         ← copied to Houdini's user preferences dir
│   ├── dso/
│   │   ├── fs/FS_Omni.dll           ← filesystem handler for omniverse:// URLs
│   │   └── OP_Omni.dll              ← Houdini operators
│   ├── python3.11libs/
│   │   ├── ready.py                 ← runs after HDAs load in all modes; elects + instantiates resolver
│   │   └── homni/                   ← Python utility module
│   ├── scripts/
│   │   ├── 456.py                   ← runs on every scene load (interactive only)
│   │   └── pythonrc.py              ← very early init, before HDAs load
│   ├── otls/                        ← compiled HDAs (Houdini Digital Assets)
│   ├── python_panels/               ← Omniverse UI panels
│   ├── husdplugins/                 ← USD export pipeline hooks
│   ├── presets/                     ← parameter presets
│   ├── toolbar/omni.shelf           ← Omniverse shelf
│   └── MainMenuCommon.xml           ← menu additions
│
└── omni/                            ← Omniverse SDK, stays alongside Houdini prefs
    ├── omni_client_library/
    │   └── omniclient.dll           ← Nucleus communication
    ├── carb_sdk_plugins/            ← Carbonite framework
    └── omni_usd_resolver/
        ├── omni_usd_resolver.dll    ← USD ArResolver plugin (built from usd-resolver repo)
        └── usd/omniverse/resolver/resources/plugInfo.json  ← USD plugin registry entry
```

---

## `houdini.env`

**Path:** `_staging/houdini21.0/houdini.env`

Houdini reads this file at startup to set environment variables. Key entries:

```ini
# Tell USD where to find the resolver's plugInfo.json
PXR_PLUGINPATH_NAME = <OMNI_ROOT>/omni_usd_resolver/usd

# Enable verbose USD plugin/resolver diagnostics (remove for production)
TF_DEBUG = AR_RESOLVER_INIT PLUG_LOAD PLUG_INFO_SEARCH

# Nucleus connection panel — leave empty so no TCP connection on startup
HOMNI_DEFAULT_CONNECTIONS =
```

`<OMNI_ROOT>` is expanded by the launcher before Houdini starts.

> **Important:** `HOMNI_DEFAULT_CONNECTIONS` must be empty or unset. If it names a Nucleus
> server that is unreachable, `FS_Omni.dll` will block the UI thread on TCP connect at startup,
> hanging Houdini's file browser (Problem 5).

---

## `houdini_launcher.bat`

The launcher sets up the environment and starts Houdini. Key responsibilities:

### PATH setup

```bat
set PATH=%OMNI_ROOT%\lib;%OMNI_ROOT%\omni_usd_resolver;%OMNI_ROOT%\omni_client_library;%HOUDINI_BIN%;%PATH%
```

`%HOUDINI_BIN%` must be on PATH so Windows' DLL loader can find Houdini's `libpxr_*.dll`
files when loading our DLL. Without it, transitive DLL dependencies fail at load time with
"The specified module could not be found."

### Version selection

```bat
houdini_launcher.bat --hver 21.0.631
```

`parse_args.bat` maps this to the correct Python version, staging folder path, and USD flavor.

---

## `plugInfo.json` (resolver)

**Path:** `_staging/houdini21.0/omni/omni_usd_resolver/usd/omniverse/resolver/resources/plugInfo.json`

USD discovers this file via `HOUDINI_USD_DSO_PATH`, which the launcher sets to:
```bat
set HOUDINI_USD_DSO_PATH=%OMNI_ROOT%\omni_usd_resolver\usd\omniverse\resolver\resources
```

USD's `Plug` library reads this to know about the resolver plugin:

```json
{
    "Plugins": [{
        "Name": "Omniverse USD Plugin",
        "Type": "library",
        "Root": "..",
        "ResourcePath": "resources",
        "LibraryPath": "../../../omni_usd_resolver.dll",
        "Info": {
            "Types": {
                "OmniUsdResolver": {
                    "bases": [ "ArResolver" ],
                    "implementsContexts": true,
                    "implementsScopedCaches": true
                },
                "OmniUsdWrapperFileFormat": {
                    "bases": [ "SdfFileFormat" ],
                    "extensions": [ "omniabc" ],
                    "formatId": "omniabc",
                    "primary": true,
                    "target": "usd"
                }
            }
        }
    }]
}
```

`LibraryPath` is relative to `Root` (`..` from the resources folder), resolving to
`omni_usd_resolver/omni_usd_resolver.dll`.

> **Do not add `uriSchemes` here.** Its presence permanently disqualifies the resolver from
> being elected as primary — it becomes a URI-only resolver (Problem 9).

---

## `ready.py` — Preferred Resolver Election

**Path:** `_staging/houdini21.0/houdini/python3.11libs/ready.py`

```python
from pxr import Ar
print("ready.py: Setting preferred resolver")
Ar.SetPreferredResolver("OmniUsdResolver")
Ar.GetResolver()
```

Houdini runs `python3.11libs/ready.py` after all HDAs load in **all modes** — interactive,
batch, and hython. This is the correct location for resolver election because:

- The resolver is elected **before** any scene file opens (no per-scene-load timing risk)
- It runs in **hython** sessions, making automated tests reliable
- `Ar.GetResolver()` eagerly instantiates the singleton so the resolver type is fixed at startup

The `AR_RESOLVER_INIT` debug log line `Using preferred resolver OmniUsdResolver` confirms
`SetPreferredResolver` runs in time. The failure in Phase 2 was not a timing issue —
the factory simply was not registered (Problem 10, Problem 13).

`456.py` (in `scripts/`) previously held this call but runs only in interactive Houdini
on scene load — too late and absent in hython.

---

## End-to-End Deployment Checklist

1. Build `usd-resolver`:
   ```bat
   cd C:\Users\rober\Documents\GitHub\usd-resolver
   repo build --usd-flavor houdini --usd-ver 25.05 --python-ver 3.11
   ```

2. Copy resolver DLL to staging:
   ```bat
   copy /Y "...\usd-resolver\_build\windows-x86_64\release\omni_usd_resolver.dll" ^
     "...\houdini-connector\_staging\houdini21.0\omni\omni_usd_resolver\omni_usd_resolver.dll"
   ```

3. Build `houdini-connector`:
   ```bat
   cd C:\Users\rober\Documents\GitHub\houdini-connector
   build_win64.bat
   ```

4. Launch Houdini:
   ```bat
   houdini_launcher.bat --hver 21.0.631
   ```

5. Verify in Houdini Python console:
   ```python
   from pxr import Plug
   reg = Plug.Registry()
   # OmniUsdResolver  isLoaded = True   ← target state
   ```
