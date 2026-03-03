pushd %~dp0

goto :init


:usage
    echo USAGE:
    echo
    echo  /?, --help           shows this help
    echo  --debug              Debug Build
    echo  --reldeb             RelWithDebInfo Build
    echo  --hver               The Houdini version to build against with. Default to 19.5
    echo  --home               Install Houdini Omni Connector plugins to home.
    echo  --keep_staging       Do not delete staging directories. This is need when you are building multiple Houdini release versions.
    exit /b 3

:init
    set "CONFIG=release"
    :: set "HOUDINI_FULL_VER=20.5.332"
    set "HOUDINI_FULL_VER=21.0.631"
    set "HOUDINI_VER=%HOUDINI_FULL_VER:~0,4%"
    set "COPY_PDBS=false"
    set "PY_VER=3.11"

:parse
    if "%~1"=="" goto :main

    if /i "%~1"=="/?"         call :usage "%~2" & goto :end
    if /i "%~1"=="-?"         call :usage "%~2" & goto :end
    if /i "%~1"=="--help"     call :usage "%~2" & goto :end
    if /i "%~1"=="-h"         call :usage "%~2" & goto :end

    if /i "%~1"=="--debug"          set "CONFIG=Debug"            & shift & goto :parse
    if /i "%~1"=="--reldeb"         set "CONFIG=RelWithDebInfo"   & shift & goto :parse
    if /i "%~1"=="--keep_staging"   set "KEEP_STAGING=true"       & shift & goto :parse
    if /i "%~1"=="--home"           set "INSTALL_HOME=true"       & shift & shift & goto :parse
    if /i "%~1"=="--hver"           set "HOUDINI_FULL_VER=%~2"    & shift & shift & goto :parse

    shift
    goto :parse

:main
    if %HOUDINI_FULL_VER% equ 19 (
        set "HOUDINI_FULL_VER=19.0"
    )

    set "HOUDINI_VER=%HOUDINI_FULL_VER:~0,4%"

    if %HOUDINI_VER% == 19.5 (
        set "PY_VER=3.9"
        set "PY_VER_INT=39"
        set "EXCLUDED_PY_VERS=*cp37* *cp38* *cp310* *cp311* *python*3*7* *python*3*8* *python*3*10* *python*3*11*"
        set "HDK_PACKAGE_VER=19.5.773"
        set "USD_FLAVOR=houdini-22_05-ar2"
    ) else if %HOUDINI_VER% == 20.0 (
        set "PY_VER=3.10"
        set "PY_VER_INT=310"
        set "EXCLUDED_PY_VERS=*cp37* *cp38* *cp39* *cp311* *python*3*7* *python*3*8* *python*3*9* *python*3*11*"
        set "HDK_PACKAGE_VER=20.0.547"
        set "USD_FLAVOR=houdini-23_08"
    ) else if %HOUDINI_VER% == 20.5 (
        set "PY_VER=3.11"
        set "PY_VER_INT=311"
        set "EXCLUDED_PY_VERS=*cp37* *cp38* *cp39* *cp310* *python*3*7* *python*3*8* *python*3*9* *python*3*10*"
        set "HDK_PACKAGE_VER=20.5.332"
        set "USD_FLAVOR=houdini-24_03"
    ) else if %HOUDINI_VER% == 21.0 (
        set "PY_VER=3.11"
        set "PY_VER_INT=311"
        set "EXCLUDED_PY_VERS=*cp37* *cp38* *cp39* *cp310* *python*3*7* *python*3*8* *python*3*9* *python*3*10*"
        set "HDK_PACKAGE_VER=21.0.631"
        :: set "USD_FLAVOR=houdini-25_05"
        set "USD_FLAVOR=houdini-24_03"
    )


    if %CONFIG% equ Debug (
        set "COPY_PDBS=true"
    )
    if %CONFIG% equ RelWithDebInfo (
        set "COPY_PDBS=true"
    )

    set HOUDINI_INSTALL=C:\Program Files\Side Effects Software\Houdini %HOUDINI_FULL_VER%
    set HOUDINI_BIN=%HOUDINI_INSTALL%\bin


:end
    exit /B
