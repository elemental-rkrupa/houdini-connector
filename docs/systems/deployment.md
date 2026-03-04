# Deployment

---

## Artist Installation

### Prerequisites

- Houdini 21.0 installed
- The connector package (contents of `_staging/houdini21.0/`) copied to an install location

### Step 1 — Copy the connector files

Copy the full contents of `_staging/houdini21.0/` to a permanent location on the artist's machine.
Recommended path (no admin rights required):

```
C:\OmniverseConnector\houdini21.0\
├── houdini\
└── omni\
```

Any path works as long as it is stable (not deleted between sessions).

### Step 2 — Install the Houdini package file

Copy [`package/omniverse.json`](../../package/omniverse.json) from this repo to the artist's
Houdini preferences packages folder:

```
%USERPROFILE%\Documents\houdini21.0\packages\omniverse.json
```

Create the `packages` folder if it does not exist.

### Step 3 — Set the install path

Open the copied `omniverse.json` and update the `HOMNI` value to match your install location
from Step 1:

```json
{
    "HOMNI" : "C:/OmniverseConnector/houdini21.0"
}
```

Use forward slashes. The rest of the file derives all paths from `HOMNI` — nothing else needs
to change.

### Step 4 — Verify

Launch Houdini 21.0. In the Python console:

```python
from pxr import Plug
for p in Plug.Registry().GetAllPlugins():
    if "omni" in p.name.lower():
        print(p.name, "isLoaded =", p.isLoaded)
```

Expected output:
```
Omniverse USD Plugin isLoaded = True
```

Alternatively, run the test suite from the repo root:
```bat
hython_launcher.bat --hver 21.0.631 -- --check_omni_plugin
```

---

## Package File Reference

**File:** [`package/omniverse.json`](../../package/omniverse.json)

The package file uses Houdini's [package system](https://www.sidefx.com/docs/houdini/ref/plugins.html)
to inject the connector's environment into Houdini at startup.

### What it does

| Key | Effect |
|-----|--------|
| `enable` | Loads only for Houdini 21.x; skipped if `HOMNI_DISABLE_PACKAGE=1` |
| `hpath` | Prepends `$HOMNI/houdini` to `HOUDINI_PATH` — loads DSOs, HDAs, scripts, panels |
| `OMNI_ROOT` | Points to the Omniverse SDK directory |
| `CARB_APP_PATH` | Required by the Carbonite plugin framework |
| `PYTHONPATH` | Adds Omniverse Python bindings so `import omni.client` works |
| `HOUDINI_USD_DSO_PATH` | Tells USD's Plug library where to find `plugInfo.json` |
| `PATH` (Windows) | Adds DLL directories so Windows finds `omniclient.dll` etc. at load time |
| `HOMNI_ENABLE_EXPERIMENTAL` | Shows experimental nodes (live sync, etc.) |

### Key differences from the Houdini 20.5 package

The `HOUDINI_USD_DSO_PATH` resolver resources path changed between versions:

| Version | Path |
|---------|------|
| 20.5 | `${OMNI_ROOT}/omni_usd_resolver/usd/omniverse/resources` |
| 21.0 | `${OMNI_ROOT}/omni_usd_resolver/usd/omniverse/resolver/resources` |

---

## Connector Layout

What the `_staging/houdini21.0/` directory contains:

```
houdini21.0/
├── houdini/                              ← added to HOUDINI_PATH
│   ├── dso/
│   │   ├── OP_Omni.dll                  ← Houdini LOP/SOP operator nodes
│   │   └── fs/FS_Omni.dll               ← filesystem handler for omniverse:// URLs
│   ├── python3.11libs/
│   │   ├── ready.py                     ← elects OmniUsdResolver as primary (all modes)
│   │   ├── pythonrc.py                  ← early init: auth dialog, expression globals
│   │   └── homni/                       ← Python utility module (logging, UI, utils)
│   ├── scripts/
│   │   └── afterscenesave.py            ← auto-checkpoint on scene save
│   ├── otls/                            ← Houdini Digital Assets (HDAs)
│   ├── husdplugins/outputprocessors/    ← USD export pipeline hooks
│   ├── python_panels/                   ← Omniverse browser UI panel
│   ├── presets/                         ← parameter presets
│   ├── toolbar/omni.shelf               ← Omniverse shelf tools
│   ├── config/Icons/                    ← toolbar and node icons
│   └── MainMenuCommon.xml               ← Omniverse menu entries
│
└── omni/                                ← Omniverse SDK (OMNI_ROOT)
    ├── lib/HoudiniOmni.dll              ← core integration library
    ├── python/                          ← homni Python bindings
    ├── carb_sdk_plugins/                ← Carbonite framework
    │   └── bindings-python/             ← Python bindings for carb modules
    ├── omni_client_library/
    │   ├── omniclient.dll               ← Nucleus communication
    │   └── bindings-python/             ← Python bindings for omni.client
    └── omni_usd_resolver/
        ├── omni_usd_resolver.dll        ← USD ArResolver plugin
        ├── bindings-python/             ← Python bindings for omni.usd_resolver
        └── usd/omniverse/resolver/resources/plugInfo.json
```

---

## `ready.py` — Resolver Election

**Path:** `houdini/python3.11libs/ready.py`

```python
from pxr import Ar
Ar.SetPreferredResolver("OmniUsdResolver")
Ar.GetResolver()
```

Houdini runs `python3.11libs/ready.py` after all HDAs load in **all modes** (interactive,
batch, hython). This is the right place for resolver election because:

- It runs before any scene file opens
- It runs in hython, making automated tests reliable
- `Ar.GetResolver()` eagerly instantiates the singleton

> **Source control gap:** `ready.py` lives only in `_staging/houdini21.0/houdini/python3.11libs/`
> which is gitignored. It is **not** tracked in the `python/python_libs/` source tree. This means
> a fresh clone does not include it. It should either be added to a tracked location (e.g.
> `python/python3.11libs/ready.py` in source, then copied to staging by the build) or checked in
> directly to `package/` or an `assets/` directory. Until then, the staging copy must be preserved
> manually.

---

## `plugInfo.json` — USD Plugin Registry

**Path:** `omni/omni_usd_resolver/usd/omniverse/resolver/resources/plugInfo.json`

USD's `Plug` library discovers this via `HOUDINI_USD_DSO_PATH` and uses it to locate and
load `omni_usd_resolver.dll`. The `LibraryPath` is relative to the plugin root:

```json
"LibraryPath": "../../../omni_usd_resolver.dll"
```

> **Do not add `uriSchemes`** to the `OmniUsdResolver` entry. Its presence permanently
> disqualifies the resolver from being elected as primary resolver.

---

## Developer Build & Deploy

After modifying `usd-resolver`, rebuild and deploy to staging:

```bash
# 1. Rebuild the resolver DLL
MSYS_NO_PATHCONV=1 "/c/Program Files/Microsoft Visual Studio/2022/Community/MSBuild/Current/Bin/MSBuild.exe" \
  "C:\\Users\\rober\\Documents\\GitHub\\usd-resolver\\_compiler\\vs2022\\OmniUsdResolver.sln" \
  /p:Configuration=release /p:Platform=x64 /t:Rebuild /verbosity:minimal

# 2. Deploy to staging
cp "_build/windows-x86_64/release/omni_usd_resolver.dll" \
   "../houdini-connector/_staging/houdini21.0/omni/omni_usd_resolver/omni_usd_resolver.dll"
```

Then test via the headless launcher:

```bat
hython_launcher.bat --hver 21.0.631 -- --check_resolver_type
hython_launcher.bat --hver 21.0.631 -- --check_omni_plugin
```

See [testing.md](testing.md) for the full test suite.

---

## `houdini.env` Coexistence

The Houdini package file (`omniverse.json`) and the artist's personal `houdini.env` are both
applied at startup and do not conflict. The package system handles all Omniverse-specific paths;
`houdini.env` is for studio-level additions (HDAs, VEX paths, etc.).

**Example coexistence** — typical artist `houdini.env` alongside the package:

```ini
# Studio HDAs (unrelated to Omniverse)
HOUDINI_PATH = G:/Shared drives/.../houdini/hda;&
HOUDINI_OTLSCAN_PATH = G:/Shared drives/.../houdini/hda;&
HOUDINI_VEX_PATH = G:/Shared drives/.../houdini/vex;&

# USD/Omniverse debug logging (uncomment to enable)
# TF_DEBUG = AR_RESOLVER_INIT PLUG_LOAD PLUG_INFO_SEARCH
```

`HOUDINI_PATH` in `houdini.env` uses `&` as the sentinel for the default Houdini path, so the
package's `hpath` contribution is still honoured.

### TF_DEBUG — USD Debug Logging

Adding `TF_DEBUG` to `houdini.env` is the recommended way to enable verbose USD resolver
logging without modifying any repo files. Useful tokens:

| Token | What it logs |
|-------|-------------|
| `AR_RESOLVER_INIT` | Which resolver is elected as primary |
| `PLUG_LOAD` | Each plugin DLL as it loads |
| `PLUG_INFO_SEARCH` | Where `Plug` searches for `plugInfo.json` |

To toggle, comment/uncomment the line in `houdini.env` — no Houdini restart required between
edits (the file is re-read at each launch).

To enable for a single hython test run without editing `houdini.env`, use:

```bat
set TF_DEBUG=AR_RESOLVER_INIT PLUG_LOAD
hython_launcher.bat --hver 21.0.631 -- --check_omni_plugin
```
