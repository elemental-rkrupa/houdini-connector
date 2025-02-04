Houdini Omniverse Connector Changelog
=====================================
200.1.0
---------------

* Changes
    *  Add Houdini Connector Installer
    *  Add Houdini 20.5 support.
    *  Update Client Library to 2.49.2
    *  Update omni.asset_validator to 0.13.2. New python module omni.asset_validator. Stop supporting omni.asset_validator.core.
    *  Update usd-resolver to 1.42.8
    *  Remove Houdini 19.0 support
    *  Remove Connect-SDK dependencies and features. Including omni.connect and omni.transcoding modules.
    *  Copy necessary MDL files when exporting USD Scenes.

200.0.1
---------------

* Changes
    *  Updated Client Library
    *  Stop using rsync for linux staging script to prevent an error in gitlab CI.
    *  Fixed an error on right click on a parameter in Houdini 20.

200.0.0
---------------

* Changes
    *  Omni Loader Houdini 20 compatibility.
    *  Remove unneeded library files.
    *  Updated OTLs so they are Houdini version backward compatible.
    *  Updated package json name to omniverse.json.
    *  Fixed an issue that redundant omni.client calls triggered when opening File Browser.
    *  Support custom carb setting toml files.
    *  Update Power Lines example HDA.
    *  Enable omni.asset_validator.core 0.10.1 python module and Omniverse Asset Validator Panel.
    *  Update logging.
    *  Use Connect SDK for config.
    *  Use Connect SDK for initializing OmniClient.
    *  Support Houdini 20.
    *  Integrate Connect SDK core 0.7.0.
    *  Updated to USD Resolver 1.40.0.
    *  Updated to Client Library 2.43.0.
    *  Carb SDK Library 160.2.
