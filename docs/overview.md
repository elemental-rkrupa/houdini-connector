# Houdini 21 Omniverse Connector — Project Overview

This project ports the **NVIDIA Omniverse Connector for Houdini** from Houdini 20.5 to **Houdini 21**,
restoring the ability for production artists to browse, load, and save USD assets on a
**cloud-based NVIDIA Nucleus server** directly from within Houdini.

NVIDIA ships no official Houdini 21 build and has stated no plans to do so. This fork compiles
and adapts the connector from NVIDIA's public source.

---

## Two Repositories, One System

The connector is split across two GitHub repos that must be built and deployed together:

| Repo | Role | Key Output |
|------|------|------------|
| [houdini-connector](https://github.com/elemental-rkrupa/houdini-connector) | Outer Houdini integration layer | `FS_Omni.dll`, `OP_Omni.dll`, Python UI, staging package |
| [usd-resolver](https://github.com/elemental-rkrupa/usd-resolver) | USD `ArResolver` C++ plugin | `omni_usd_resolver.dll` |

Both are personal forks of the upstream `NVIDIA-Omniverse` originals.

```
usd-resolver/
  └─ build → omni_usd_resolver.dll
                    │
                    ▼ (manual copy)
houdini-connector/
  └─ _staging/houdini21.0/
       ├─ houdini/dso/          ← FS_Omni.dll, OP_Omni.dll
       ├─ omni/omni_usd_resolver/  ← omni_usd_resolver.dll
       ├─ houdini.env           ← environment / debug flags
       └─ omni/omni_usd_resolver/usd/plugInfo.json  ← USD plugin registry entry
```

---

## Subsystem Documentation

| Document | Covers |
|----------|--------|
| [systems/resolver.md](systems/resolver.md) | `omni_usd_resolver.dll` — USD AR plugin, registration chain, Windows DLL boundary issues |
| [systems/connector.md](systems/connector.md) | `FS_Omni`, `OP_Omni`, `HoudiniOmni`, Python UI panels |
| [systems/build.md](systems/build.md) | Build commands, dependencies, toolchain requirements |
| [systems/deployment.md](systems/deployment.md) | Staging layout, `houdini.env`, launcher, deploy step |
| [systems/testing.md](systems/testing.md) | Hython headless launcher, test scripts, how to run and extend tests |
| [systems/debugging.md](systems/debugging.md) | Diagnostic commands, log lines, current blocker, next steps |

---

## Current Status

| Phase | Status |
|-------|--------|
| Phase 1 — houdini-connector builds and deploys | Complete |
| Phase 2 — `omni_usd_resolver.dll` builds, loads, exports symbols | Complete |
| `TF_REGISTRY_FUNCTION` fires / factory registered | **Blocked** — `.pxrctor` section absent from DLL |
| `omniverse://` path resolution working end-to-end | Not yet reached |

See [systems/debugging.md](systems/debugging.md) for the outstanding blocker and recommended next steps.

---

## Key Version Constraints

| Component | Version |
|-----------|---------|
| Houdini | 21.0.631 |
| USD | 25.05 (`pxrInternal_v0_25_5__pxrReserved__`) |
| Python | 3.11 |
| Qt / PySide | PySide6 |
| Compiler | MSVC via Visual Studio 2022 Community |
| Build tool | premake5 → VS2022 → MSBuild |

The USD C++ namespace (`pxrInternal_v0_25_5__pxrReserved__`) must match exactly between
`omni_usd_resolver.dll` and Houdini's own `libpxr_*.dll` files. Any mismatch produces silent
failures with no "wrong version" error.

---

## Development History

Full problem-by-problem breakdown of what was changed and why:
[development_history.md](development_history.md)
