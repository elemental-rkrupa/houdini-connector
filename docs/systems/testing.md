# Testing via Hython

---

## Overview

Interactive Houdini is not suitable for autonomous testing. Instead, a headless launcher
(`hython_launcher.bat`) starts **Hython** — Houdini's embedded Python interpreter with the full
application environment loaded but no UI. Test scripts in `Tests/connector_tests/` are passed
as arguments to Hython.

This allows the full connector + resolver stack to be exercised without a running Houdini GUI session.

---

## Launcher

**File:** [hython_launcher.bat](../../houdini-connector/hython_launcher.bat)

A derivative of `houdini_launcher.bat`. Sets up the same environment (DLL paths, `PYTHONPATH`,
`HOUDINI_PATH`, `HOUDINI_USD_DSO_PATH`, etc.) but calls `hython.exe` instead of `houdini.exe`.

### Usage

```bat
hython_launcher.bat --hver 21.0.631 [--debug] [TEST_ARG]
```

`%3` is the third positional argument (after `--hver` and the version number).

With no test argument, Hython drops to an interactive Python prompt (useful for manual investigation).

### How test args are dispatched

```bat
if "%3"=="--quit"                   SET "CMD=.\Tests\connector_tests\quit.py file"
if "%3"=="--init_resolvers"         SET "CMD=.\Tests\connector_tests\init_resolvers.py file"
if "%3"=="--list_plugins"           SET "CMD=.\Tests\connector_tests\list_usd_plugins_status.py file"
if "%3"=="--check_env"              SET "CMD=.\Tests\connector_tests\check_env.py file"
if "%3"=="--check_omni_plugin"      SET "CMD=.\Tests\connector_tests\check_omni_plugin.py file"
if "%3"=="--check_resolver_type"    SET "CMD=.\Tests\connector_tests\check_resolver_type.py file"
if "%3"=="--set_preferred_resolver" SET "CMD=.\Tests\connector_tests\set_preferred_resolver.py file"

call "%HOUDINI_BIN%\hython.exe" %CMD%
```

---

## Test Scripts

**Folder:** [Tests/connector_tests/](../../houdini-connector/Tests/connector_tests/)

The tests form a progressive probe — each step presupposes the previous one passed.
Run them in the order listed below when diagnosing a failure.

---

### `--quit` — Smoke test / baseline

```bat
hython_launcher.bat --hver 21.0.631 --quit
```

Just starts Hython and immediately exits. If this fails or hangs there is a fundamental
problem: a DLL cannot be found on PATH, an environment variable is misconfigured, or a DLL's
static initialisers are crashing on load.

**This is the minimum bar — everything else depends on it passing cleanly.**

Expected: process exits cleanly, no error output.

---

### `--check_env` — Environment sanity check

```bat
hython_launcher.bat --hver 21.0.631 --check_env
```

Verifies key environment variables are set and critical files exist at the expected paths:

- `OMNI_ROOT`, `HOUDINI_PATH`, `HOUDINI_USD_DSO_PATH`, `HOUDINI_BIN` are set
- `omni_usd_resolver.dll` exists under `OMNI_ROOT`
- `plugInfo.json` exists at the correct resources path
- `omniclient.dll` exists
- `PATH` contains the DLL directories

Run this first if `--quit` fails — it will pinpoint missing files or env vars without
needing to interpret USD log output.

---

### `--list_plugins` — Plugin registry dump

```bat
hython_launcher.bat --hver 21.0.631 --list_plugins
```

Lists every USD plugin in Houdini's Plug registry and its load status. Confirms:

- `Omniverse USD Plugin` appears (means `plugInfo.json` was discovered via `HOUDINI_USD_DSO_PATH`)
- `isLoaded = True` (means the DLL loaded and its static initialisers ran without crashing)

If `isLoaded = False`, the DLL was found by the registry but failed to load. Check PATH and
enable `TF_DEBUG=PLUG_LOAD`.

---

### `--check_omni_plugin` — Focused Omniverse plugin check

```bat
hython_launcher.bat --hver 21.0.631 --check_omni_plugin
```

Same intent as `--list_plugins` but focused on the Omniverse plugin only, with explicit
PASS/FAIL output and diagnostic hints. Easier to read than the full plugin list.

---

### `--init_resolvers` — Resolver instantiation (minimal)

```bat
hython_launcher.bat --hver 21.0.631 --init_resolvers
```

Calls `Ar.GetResolver()` and exits. This forces USD to manufacture the primary resolver.
Watch `TF_DEBUG` output — this is where the current `.pxrctor` blocker manifests:

| TF_DEBUG line | Meaning |
|---------------|---------|
| `Using preferred resolver OmniUsdResolver` | `ready.py` → `ArSetPreferredResolver` ran correctly |
| `Failed to manufacture asset resolver OmniUsdResolver` | Factory null — `.pxrctor` issue |
| `Using default asset resolver ArDefaultResolver` | Fallback — resolver did not instantiate |

---

### `--check_resolver_type` — Resolver type with explicit PASS/FAIL

```bat
hython_launcher.bat --hver 21.0.631 --check_resolver_type
```

Calls `Ar.GetResolver()` and prints the actual Python type of the returned resolver with
an explicit PASS/FAIL verdict. **This is the definitive test for the current blocker.**

Expected (working): `PASS: OmniUsdResolver is active as primary resolver`
Current (blocked):  `FAIL: Expected OmniUsdResolver, got ArDefaultResolver`

---

### `--set_preferred_resolver` — Explicit preferred resolver + instantiation

```bat
hython_launcher.bat --hver 21.0.631 --set_preferred_resolver
```

Explicitly calls `Ar.SetPreferredResolver("OmniUsdResolver")` then `Ar.GetResolver()`,
mirroring what `ready.py` does at startup. Since `ready.py` also runs in hython and calls
`Ar.GetResolver()` eagerly, the resolver singleton is already instantiated by the time any
test script runs — this test is most useful for verifying behaviour in isolation or confirming
the factory is reachable at all if `ready.py` is suspected of not running.

---

## Enabling TF_DEBUG Output

Add to `houdini.env` or set temporarily in the launcher before the `hython.exe` call:

```bat
set TF_DEBUG=AR_RESOLVER_INIT PLUG_LOAD PLUG_INFO_SEARCH
```

Essential for diagnosing resolver initialisation failures — see [debugging.md](debugging.md)
for the full log line reference.

---

## Recommended Run Order (Diagnosing from Scratch)

```bat
hython_launcher.bat --hver 21.0.631 --quit                    :: 1. Does it start?
hython_launcher.bat --hver 21.0.631 --check_env               :: 2. Files and env vars present?
hython_launcher.bat --hver 21.0.631 --check_omni_plugin       :: 3. DLL found and loaded?
hython_launcher.bat --hver 21.0.631 --check_resolver_type     :: 4. Factory registered? (current blocker)
hython_launcher.bat --hver 21.0.631 --set_preferred_resolver  :: 5. Factory reachable after explicit elect?
```

---

## Adding a New Test

1. Create a Python script in `Tests/connector_tests/` ending with `quit()`
2. Add a handler in `hython_launcher.bat`:
   ```bat
   if "%3"=="--your_flag" ( SET "CMD=.\Tests\connector_tests\your_script.py file" )
   ```

### Tests to add when resolver is working

| Flag | Script | What to test |
|------|--------|--------------|
| `--resolve_local` | `resolve_local_path.py` | `Ar.GetResolver().Resolve("C:/tmp/test.usd")` — basic file resolution |
| `--resolve_omni` | `resolve_omni_path.py` | `Ar.GetResolver().Resolve("omniverse://localhost/test.usd")` — requires Nucleus |
| `--open_layer` | `open_usd_layer.py` | `Sdf.Layer.FindOrOpen("omniverse://...")` — full layer load |
