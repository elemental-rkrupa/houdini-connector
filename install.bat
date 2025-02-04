@echo off
setlocal enabledelayedexpansion

call .\parse_args.bat %*
:: Exit due to passing -h --help -? /? flag
if errorlevel 3 exit /b 0

pushd %~dp0


if NOT "%KEEP_STAGING%" == "true" (
    if exist %~dp0_staging\ (
        rmdir %~dp0_staging /s /q
    )
)

if defined INSTALL_HOME goto InstallHome

set INSTALL_BASE=%~dp0_staging\houdini%HOUDINI_VER%

goto DoInstall


:: Define the functions
:InstallHome
if exist %USERPROFILE%\Documents\houdini%HOUDINI_VER% (
    set INSTALL_BASE=%USERPROFILE%\Documents\houdini%HOUDINI_VER%
) else (
    if exist %USERPROFILE%\houdini%HOUDINI_VER% (
        set INSTALL_BASE=%USERPROFILE%\houdini%HOUDINI_VER%
    ) else (
        echo "Could not find Houdini %HOUDINI_VER% plugin folder."
        pause
        exit /b 2
    )
)
goto :eof


:link_files
set "SOURCE_DIR=%~1"
set "FILE_PATTERN=%~2"
set "TARGET_DIR=%~3"

:: Create hard links
if not exist %TARGET_DIR% mkdir %TARGET_DIR%
for /f %%k in ('dir "%SOURCE_DIR%\%FILE_PATTERN%" /b') do (
    mklink /H "%TARGET_DIR%\%%~k" "%SOURCE_DIR%\%%~nxk"
)
goto :eof


:link_dirs
set "SOURCE_DIR=%~1"
set "TARGET_DIR=%~2"

:: Create hard links
if not exist %TARGET_DIR% mkdir %TARGET_DIR%
for /f %%k in ('dir "%SOURCE_DIR%" /b /ad') do (
    mklink /J "%TARGET_DIR%\%%~k" "%SOURCE_DIR%\%%~nxk"
)
goto :eof


:copy_dirs
set "SOURCE_DIR=%~1"
set "TARGET_DIR=%~2"

:: Copy dirs
if not exist %TARGET_DIR% mkdir %TARGET_DIR%
for /f %%k in ('dir "%SOURCE_DIR%" /b /ad') do (
    xcopy "%SOURCE_DIR%\%%~k" "%TARGET_DIR%\%%~nxk" /f /i /y /r /e
)
goto :eof


:DoInstall
set HOUDINI_BASE=%INSTALL_BASE%\houdini
set OMNI_BASE=%INSTALL_BASE%\omni
set BINDINGS_PYTHON=%OMNI_BASE%\python

echo Installing plugins for %CONFIG% configuration.
:: Copy homni dll files
xcopy %~dp0_build\OP_Omni\%CONFIG%\OP_Omni.dll %HOUDINI_BASE%\dso\ /f /i /y /r
xcopy %~dp0_build\FS_Omni\%CONFIG%\FS_Omni.dll %HOUDINI_BASE%\dso\fs\ /f /i /y /r
xcopy %~dp0_build\HoudiniOmni\%CONFIG%\HoudiniOmni.dll %OMNI_BASE%\lib\ /f /i /y /r
xcopy %~dp0_build\HoudiniOmniPy\%CONFIG%\client.pyd %BINDINGS_PYTHON%\homni\ /f /i /y /r
:: Copy homni __init__.py
xcopy %~dp0python\python_libs\homni\__init__.py %BINDINGS_PYTHON%\homni\ /f /i /y /r

:: plugins files
xcopy %~dp0_build\target-deps\carb_sdk_plugins\_build\windows-x86_64\%CONFIG%\carb.dll %OMNI_BASE%\lib\

:: python files
:: Asset Validator python files
xcopy %~dp0_build\target-deps\omni_asset_validator\python\omni\*  %BINDINGS_PYTHON%\omni\  /f /i /y /r /e

:: Copy target-deps\{packages} to staging\{package}
xcopy %~dp0_build\target-deps\omni_usd_resolver\%CONFIG%\ %OMNI_BASE%\omni_usd_resolver\ /f /i /y /r /e
robocopy %~dp0_build\target-deps\omni_client_library\%CONFIG%\ %OMNI_BASE%\omni_client_library\ /s /xf %EXCLUDED_PY_VERS%
robocopy %~dp0_build\target-deps\carb_sdk_plugins\_build\windows-x86_64\%CONFIG%\bindings-python\ %OMNI_BASE%\carb_sdk_plugins\bindings-python\ /s /xf %EXCLUDED_PY_VERS%

:: Houdini dir
:: Copy pythonrc.py
xcopy %~dp0python\python_libs\pythonrc.py %HOUDINI_BASE%\python%PY_VER%libs\ /f /y /r
xcopy %~dp0houdini-help\command.help %HOUDINI_BASE%\help\ /f /i /y /r
xcopy %~dp0assets\help\nodes\lop\* %HOUDINI_BASE%\help\nodes\lop\ /f /i /y /r
xcopy %~dp0assets\help\nodes\other\* %HOUDINI_BASE%\help\nodes\other\ /f /i /y /r

xcopy %~dp0python\python_libs\homni %HOUDINI_BASE%\python%PY_VER%libs\homni /s /f /i /y /r

xcopy %~dp0assets\MainMenuCommon.xml %HOUDINI_BASE%\ /f /i /y /r
xcopy %~dp0assets\PARMmenu.xml %HOUDINI_BASE%\ /f /i /y /r

xcopy %~dp0assets\scripts\menu_omni_connect.py %HOUDINI_BASE%\scripts\ /f /i /y /r
xcopy %~dp0assets\scripts\menu_omni_panel.py %HOUDINI_BASE%\scripts\ /f /i /y /r
xcopy %~dp0assets\scripts\afterscenesave.py %HOUDINI_BASE%\scripts\ /f /i /y /r

xcopy %~dp0assets\python_panels\Omniverse.pypanel %HOUDINI_BASE%\python_panels\ /f /i /y /r
xcopy %~dp0assets\python_panels\AssetValidator.pypanel %HOUDINI_BASE%\python_panels\ /f /i /y /r

:: Copy icons
xcopy %~dp0assets\config\Icons\nvidia-omniverse.ico %HOUDINI_BASE%\config\Icons\ /f /i /y /r
xcopy %~dp0assets\config\Icons\LOP_omni_live_sync.png %HOUDINI_BASE%\config\Icons\ /f /i /y /r

xcopy %~dp0assets\presets\Driver\usd.idx %HOUDINI_BASE%\presets\Driver\ /f /i /y /r
xcopy %~dp0assets\presets\Lop\usd_rop.idx %HOUDINI_BASE%\presets\Lop\ /f /i /y /r
xcopy %~dp0assets\presets\Lop\copyproperty.idx %HOUDINI_BASE%\presets\Lop\ /f /i /y /r
xcopy %~dp0assets\presets\Lop\editproperties.idx %HOUDINI_BASE%\presets\Lop\ /f /i /y /r
xcopy %~dp0assets\presets\Vop\mdlomnihair.idx %HOUDINI_BASE%\presets\Vop\ /f /i /y /r
xcopy %~dp0assets\presets\Vop\mdlomnisurface_lite.idx %HOUDINI_BASE%\presets\Vop\ /f /i /y /r
xcopy %~dp0assets\presets\Vop\mdlomnisurface.idx %HOUDINI_BASE%\presets\Vop\ /f /i /y /r

xcopy %~dp0assets\toolbar\omni.shelf %HOUDINI_BASE%\toolbar\ /f /i /y /r

xcopy %~dp0assets\husdplugins\outputprocessors\omnitextureexport.py %HOUDINI_BASE%\husdplugins\outputprocessors\ /f /i /y /r
xcopy %~dp0assets\husdplugins\outputprocessors\omnicheckpoints.py %HOUDINI_BASE%\husdplugins\outputprocessors\ /f /i /y /r
xcopy %~dp0assets\husdplugins\outputprocessors\omnimdlproperties.py %HOUDINI_BASE%\husdplugins\outputprocessors\ /f /i /y /r
xcopy %~dp0assets\husdplugins\outputprocessors\omnisimplerelativepaths.py %HOUDINI_BASE%\husdplugins\outputprocessors\ /f /i /y /r
xcopy %~dp0assets\husdplugins\outputprocessors\omniusdformat.py %HOUDINI_BASE%\husdplugins\outputprocessors\ /f /i /y /r

xcopy %~dp0assets\husdplugins\shadertranslators\mdl.py %HOUDINI_BASE%\husdplugins\shadertranslators\ /f /i /y /r

xcopy %~dp0assets\otls\mdl_omnipbr_vop.hda %HOUDINI_BASE%\otls\ /f /i /y /r
xcopy %~dp0assets\otls\mdl_omnivolumedensity_vop.hda %HOUDINI_BASE%\otls\ /f /i /y /r
xcopy %~dp0assets\otls\mdl_omniglass_vop.hda %HOUDINI_BASE%\otls\ /f /i /y /r
xcopy %~dp0assets\otls\mdl_omnihair_vop.hda %HOUDINI_BASE%\otls\ /f /i /y /r
xcopy %~dp0assets\otls\mdl_omnipbrclearcoat_vop.hda %HOUDINI_BASE%\otls\ /f /i /y /r
xcopy %~dp0assets\otls\mdl_omnisurface_vop.hda %HOUDINI_BASE%\otls\ /f /i /y /r
xcopy %~dp0assets\otls\mdl_omnisurfacelite_vop.hda %HOUDINI_BASE%\otls\ /f /i /y /r
xcopy %~dp0assets\otls\omni_editmdl.hda %HOUDINI_BASE%\otls\ /f /i /y /r
xcopy %~dp0assets\otls\object_omni_examplePowerlines.hda %HOUDINI_BASE%\otls\ /f /i /y /r
xcopy %~dp0assets\otls\omni_liveeditbreak.hda %HOUDINI_BASE%\otls\ /f /i /y /r
xcopy %~dp0assets\otls\omni_loader.hda %HOUDINI_BASE%\otls\ /f /i /y /r
xcopy %~dp0assets\otls\omni_validator.hda %HOUDINI_BASE%\otls\ /f /i /y /r
xcopy %~dp0assets\otls\omni_lights.hda %HOUDINI_BASE%\otls\ /f /i /y /r
xcopy %~dp0assets\otls\omni_conform.hda %HOUDINI_BASE%\otls\ /f /i /y /r
xcopy %~dp0assets\otls\sop_omni_frustum.hda %HOUDINI_BASE%\otls\ /f /i /y /r

:: Version specific files
if %HOUDINI_VER% == 19.0 (
    xcopy %~dp0assets%HOUDINI_VER%\presets\Lop\usd_rop.idx %HOUDINI_BASE%\presets\Lop\ /f /i /y /r
    xcopy %~dp0assets%HOUDINI_VER%\presets\Driver\usd.idx %HOUDINI_BASE%\presets\Driver\ /f /i /y /r
    xcopy %~dp0assets%HOUDINI_VER%\otls\omni_editmdl.hda %HOUDINI_BASE%\otls\ /f /i /y /r
    xcopy %~dp0assets%HOUDINI_VER%\otls\omni_validator.hda %HOUDINI_BASE%\otls\ /f /i /y /r
    xcopy %~dp0assets%HOUDINI_VER%\otls\omni_lights.hda %HOUDINI_BASE%\otls\ /f /i /y /r
    xcopy %~dp0assets%HOUDINI_VER%\otls\object_omni_examplePowerlines.hda %HOUDINI_BASE%\otls\ /f /i /y /r
) else if %HOUDINI_VER% == 19.5 (
    xcopy %~dp0assets%HOUDINI_VER%\presets\Lop\usd_rop.idx %HOUDINI_BASE%\presets\Lop\ /f /i /y /r
    xcopy %~dp0assets%HOUDINI_VER%\presets\Driver\usd.idx %HOUDINI_BASE%\presets\Driver\ /f /i /y /r
    xcopy %~dp0assets%HOUDINI_VER%\otls\omni_editmdl.hda %HOUDINI_BASE%\otls\ /f /i /y /r
    xcopy %~dp0assets%HOUDINI_VER%\otls\object_omni_examplePowerlines.hda %HOUDINI_BASE%\otls\ /f /i /y /r
)

if %COPY_PDBS% equ true (
    xcopy %~dp0_build\OP_Omni\%CONFIG%\OP_Omni.pdb %HOUDINI_BASE%"\dso\" /f /i /y /r
    xcopy %~dp0_build\FS_Omni\%CONFIG%\FS_Omni.pdb %HOUDINI_BASE%"\dso\fs\" /f /i /y /r
    xcopy %~dp0_build\HoudiniOmni\%CONFIG%\HoudiniOmni.pdb %OMNI_BASE%\ /f /i /y /r
    xcopy %~dp0_build\HoudiniOmniPy\%CONFIG%\client.pdb %BINDINGS_PYTHON%\homni\ /f /i /y /r
)

goto :eof

exit /b 0
