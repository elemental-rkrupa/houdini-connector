# Build System

---

## Overview

Both repos use **NVIDIA's `repo` tool** (a wrapper around packman + premake/CMake) to manage
dependencies and generate project files. The build pipeline is:

```
repo build → packman fetches deps → premake5 generates .sln → MSBuild compiles
```

The two repos are built independently. `usd-resolver` must be built first, then its DLL is
copied into `houdini-connector`'s staging folder.

---

## usd-resolver Build

### Commands

```bat
cd C:\Users\rober\Documents\GitHub\usd-resolver

:: Full build (generates project files + compiles)
repo build --usd-flavor houdini --usd-ver 25.05 --python-ver 3.11

:: Rebuild without regenerating project files (faster, use after source-only changes)
"C:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\MSBuild.exe" ^
  "C:\Users\rober\Documents\GitHub\usd-resolver\_compiler\vs2022\OmniUsdResolver.sln" ^
  /p:Configuration=release;Platform=x64 /t:Rebuild /verbosity:minimal
```

> `repo build --rebuild` regenerates project files but does **not** do an MSBuild clean+rebuild.
> Use the MSBuild `/t:Rebuild` command to force full recompilation without re-running premake.

### Build Output

| Path | Contents |
|------|---------|
| `_build/windows-x86_64/release/omni_usd_resolver.dll` | The resolver DLL |
| `_compiler/vs2022/OmniUsdResolver.sln` | Generated Visual Studio solution |
| `_compiler/vs2022/omni_usd_resolver/omni_usd_resolver.vcxproj` | Generated project file |

### Key Build Configuration — `premake5.lua`

| Setting | Value | Reason |
|---------|-------|--------|
| `vs_version` | `vs2022` | Pin to VS2022 (was auto-detect before) |
| `vs_path` | `C:\Program Files\Microsoft Visual Studio\2022\Community` | Explicit VS path |
| `libdirs` | `C:/Program Files/.../Houdini 21.0.631/custom/houdini/dsolib` | Houdini's .lib location |
| `links` | `libpxr_boost`, `libpxr_python`, `libpxr_ar` | USD 25.05 requires explicit linking |
| `defines` | `ARCH_OS_WINDOWS` | Belt-and-suspenders Windows branch selection |
| `defines` | `MFB_ALT_PACKAGE_NAME=omni_usd_resolver` | Required for `.pxrctor` section emission |

### Dependencies

| Dependency | Location | How Acquired |
|------------|----------|--------------|
| USD 25.05 headers | `C:/Program Files/Side Effects Software/Houdini 21.0.631/toolkit/include/` | Houdini install |
| Houdini import libs | `C:/Program Files/Side Effects Software/Houdini 21.0.631/custom/houdini/dsolib/` | Houdini install |
| Pre-extracted USD headers | `C:/tmp/usd-resolver-deps/` | Manually extracted |
| Omniverse client library | `_build/target-deps/omni_client_library/` | Fetched by packman |
| Python 3.11 | `_build/usd-deps/python/` | Fetched by packman |

---

## houdini-connector Build

### Commands

```bat
cd C:\Users\rober\Documents\GitHub\houdini-connector

:: Full build
build_win64.bat

:: Debug build
build_win64.bat --debug
```

### Build Flags — `parse_args.bat`

A Houdini 21.0 block was added to `parse_args.bat` (Problem 3 fix). Default version is now 21.0.631:

```bat
set "HOUDINI_FULL_VER=21.0.631"
...
) else if %HOUDINI_VER% == 21.0 (
    set "PY_VER=3.11"
    set "PY_VER_INT=311"
    set "HDK_PACKAGE_VER=21.0.631"
    set "USD_FLAVOR=houdini-24_03"
)
```

> `USD_FLAVOR=houdini-24_03` is used only to satisfy the packman download step for the binary
> `omni_usd_resolver`. That binary is replaced by the locally built DLL from `usd-resolver`.
> No `houdini-25_05` packman flavor exists on NVIDIA's servers.

### Key Build Dependencies

| Dependency | Source |
|------------|--------|
| Houdini 21 HDK | `C:\Program Files\Side Effects Software\Houdini 21.0.631\toolkit\` |
| `libpxr_python.lib`, `libpxr_boost.lib` | `C:\Program Files\Side Effects Software\Houdini 21.0.631\custom\houdini\dsolib\` |
| Omniverse client library | packman / `_build/target-deps/omni_client_library/` |

### PySide2 → PySide6 Migration (Problem 4)

All Python source files under `houdini/python3.11libs/` and `python/` must use `PySide6` imports.
Search for remaining `PySide2` references:

```bat
findstr /s /i "PySide2" "C:\Users\rober\Documents\GitHub\houdini-connector\*.py"
```

After updating source files, clear stale bytecode:

```bat
del /s /q "_staging\houdini21.0\houdini\python3.11libs\*.pyc"
for /d /r "_staging\houdini21.0" %d in (__pycache__) do @if exist "%d" rd /s /q "%d"
```

---

## Deploy Step (Manual)

After building `usd-resolver`, copy the DLL into the connector's staging folder:

```bat
copy /Y ^
  "C:\Users\rober\Documents\GitHub\usd-resolver\_build\windows-x86_64\release\omni_usd_resolver.dll" ^
  "C:\Users\rober\Documents\GitHub\houdini-connector\_staging\houdini21.0\omni\omni_usd_resolver\omni_usd_resolver.dll"
```

This step is manual — there is no automated integration between the two build systems.

---

## Verifying the Build

### Check USD namespace in resolver exports

```bat
dumpbin /exports omni_usd_resolver.dll | findstr /i "OmniUsdResolver"
```

All symbols must be in `pxrInternal_v0_25_5__pxrReserved__`.

### Check `.pxrctor` section present

```bat
dumpbin /headers omni_usd_resolver.dll | findstr /i "pxrctor"
```

If absent, `TF_REGISTRY_FUNCTION` will never fire. Check the `.obj` first to distinguish
macro expansion failure from linker stripping:

```bat
dumpbin /headers "_build\intermediate\windows\omni_usd_resolver\x86_64\release\OmniUsdResolver_Ar2.obj" > obj.txt
findstr /i "pxrctor" obj.txt
```

### Check defines are in the generated vcxproj

```bat
findstr /i "PreprocessorDefinitions" ^
  "_compiler\vs2022\omni_usd_resolver\omni_usd_resolver.vcxproj"
```

Must contain `ARCH_OS_WINDOWS` and `MFB_ALT_PACKAGE_NAME=omni_usd_resolver`.
