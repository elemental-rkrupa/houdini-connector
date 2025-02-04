# Houdini Omniverse Plugin

An Omniverse connector plugin for Houdini that integrates the Omniverse Client Library to support resolving Omniverse URLs in Houdini's file system and in the USD context.

## Pre-Requisites

The following dependencies need to be available on your PC to build this Connector:

* houdini_usd

    * Note the folder structure should be as follows:
    
        ```bash
        houdini_usd
        ├── include
        │   ├── Alembic
        │   ├── boost
        │   ├── draco
        │   ├── hboost
        │   ├── libpng16
        │   ├── MaterialXCore
        │   ├── MaterialXFormat
        │   ├── MaterialXGenGlsl
        │   ├── MaterialXGenMdl
        │   ├── MaterialXGenMsl
        │   ├── MaterialXGenOsl
        │   ├── MaterialXGenShader
        │   ├── MaterialXRender
        │   ├── MaterialXRenderGlsl
        │   ├── MaterialXRenderHw
        │   ├── MaterialXRenderOsl
        │   ├── OpenEXR
        │   ├── OpenImageIO
        │   ├── opensubdiv
        │   ├── pxr
        │   ├── python3.11
        │   ├── serial
        │   └── tbb
        └── lib
            ├── python
            └── usd_plugins
        ```
* houdini_hdk
    
    * Note the folder structure should be as follows:

        ```bash
        houdini_hdk
        ├── dsolib
        │   ├── empty_jemalloc
        │   ├── Qt_plugins
        │   └── usd_plugins
        ├── python311       
        │   ├── bin
        │   ├── include
        │   ├── lib
        │   └── share
        └── toolkit
            ├── cmake   
            ├── codegenTemplates
            ├── include
            ├── makefiles
            ├── samples
            └── slides
        ```

* **NOTICE:** This project will download and install additional third-party open source software projects. Review the license terms of these open source projects before use.

### Configuring locations of houdini dependencies

1. Navigate to the following file within this repository and open, `./deps/target-deps.packman.xml`
2. You must uncomment the block of code for `houdini_usd` and `houdini_hdk`and replace the path with your local copy
```xml
 <!-- External Devs should replace "path" to their local Houdini USD path -->
    <dependency name="usd" linkPath="../_build/target-deps/usd/${config}"> 
        <source path="C:\path\to\houdini_usd\containing\include\and\lib\folders"/> 
    </dependency> 
```
3. Once these path variables have been updated for both dependencies, you are now able to move to the [Building](#building) step.

## Building

Please run the following to build the plugins:

### Windows
``` bash
.\build_win64.bat
```

### Linux
```bash
./build_linux.sh
```

Running the build script will install the compiled plugin binaries and additional resources (scripts, otls, etc.) to a _staging project subdirectory.

- Linux has been built with gcc 9.2.0 binutils with glib 2.30 for x86_64 Linux GNU 6

## Build configurations

By default, the build_win64.bat script will build and install the Release configuration of the plugin.  This script may also be called with either the --debug or --reldeb flags to build and install the Debug and RelWithDebInfo configurations, respectively.

Example usage:

.\build_win64.bat --reldeb

## Testing

### Test Houdini Launcher

To test the Houdini launcher, follow these steps:

1. **Run the Launcher Script**

   Execute the following command in your terminal:

   ```bash
   .\houdini_launcher.{bat/sh}
   ```

   This script sets the necessary Houdini paths to load the compiled plugin from the `_staging` directory and launches the Houdini executable.

2. **Specify Houdini Version (Optional)**

   By default, the launcher uses Houdini version **19.5.303**. To override this default version, use the `--hver` argument followed by the desired version number. For example:

   ```bash
   .\houdini19_launcher.bat --hver 19.5.303
   ```

### Houdini Test Suite

To execute the complete test suite, run the following command:

  ```bash
  .\run_tests.{bat/sh}
  ```

Note: You can specify a Houdini version when running the tests by adding the `--hver` argument followed by the version number. For example:

```bash
./run_tests.sh --hver 19.5.303
```

## Local Omniverse cache location

The plugin may save temporary files to the cache directory on the local machine (typically %USERPROFILE%/Documents/Omniverse/Houdini/\<server>/).

