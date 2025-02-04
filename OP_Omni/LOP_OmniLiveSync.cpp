// SPDX-FileCopyrightText: Copyright (c) 2021-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: LicenseRef-NvidiaProprietary
//
// NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
// property and proprietary rights in and to this material, related
// documentation and any modifications thereto. Any use, reproduction,
// disclosure or distribution of this material and related documentation
// without an express license agreement from NVIDIA CORPORATION or
// its affiliates is strictly prohibited.

// The following include is needed to avoid a link error for
// debug builds, where python27_d.lib can't be found.  See
// the comments near the top of wrap_python_fixed_for_debug.hpp.

#ifndef NDEBUG
#    include "wrap_python_fixed_for_debug.hpp"
#endif
#include "HoudiniOmni.h"
#include "HoudiniOmniResultTypes.h"
#include "HoudiniOmniUtils.h"
#include "LOP_OmniLiveSync.h"

#include <CH/CH_Manager.h>
#include <HUSD/HUSD_Constants.h>
#include <HUSD/HUSD_CreatePrims.h>
#include <HUSD/HUSD_Utils.h>
#include <HUSD/XUSD_Data.h>
#include <HUSD/XUSD_Utils.h>
#include <LOP/LOP_Error.h>
#include <LOP/LOP_PRMShared.h>
#include <OP/OP_Operator.h>
#include <OP/OP_OperatorTable.h>
#include <PRM/PRM_Include.h>
#include <iostream>
#include <pxr/usd/sdf/copyUtils.h>
#include <pxr/usd/sdf/layer.h>
#include <pxr/usd/sdf/path.h>
#include <pxr/usd/usd/attribute.h>
#include <pxr/usd/usd/stage.h>
#include <pxr/usd/usdGeom/tokens.h>
#include <pxr/usd/usdGeom/xformCommonAPI.h>
#include <pxr/usd/usdGeom/xformable.h>
#include <pxr/usd/usdUtils/flattenLayerStack.h>
#include <stack>
#include <vector>

using namespace homni;
PXR_NAMESPACE_USING_DIRECTIVE

void newLopOperator(OP_OperatorTable* table)
{
    std::string env = homni::OmniUtils::getEnvVar("HOMNI_ENABLE_EXPERIMENTAL");

    if (env == "1")
    {
        table->addOperator(
            new OP_Operator("omni_live_sync", "Omniverse Live Sync", LOP_OmniLiveSync::myConstructor, LOP_OmniLiveSync::myTemplateList, 1u, 1u));
    }
}

static PRM_Name theCreateLiveLayerName("createlivelayer", "Create Live Layer");
static PRM_Name theSaveLiveLayerName("savelivelayer", "Save Live Layer");
static PRM_Name theClearLiveLayerName("clearlivelayer", "Clear Live Layer");
static PRM_Name theReloadLiveLayerName("reloadlivelayer", "Reload Live Layer");
static PRM_Name theLiveSyncName("livesync", "Live Sync");
static PRM_Name theLiveFileName("livefile", "Live File");
static PRM_Name theUsdFileName("usdfile", "USD File");

static PRM_Default theLiveFileDefault(0, "omniverse://localhost/Users/test/houdini_live_edit.live");
static PRM_Default theLUsdFileDefault(0, "omniverse://localhost/Users/test/houdini_live_edit.usd");

static PRM_Name theSyncModes[] = { PRM_Name("push", "Push"), PRM_Name("pull", "Pull"), PRM_Name() };
static PRM_ChoiceList theSyncModeMenu(PRM_CHOICELIST_SINGLE, theSyncModes);
static PRM_Name theSyncModeName("syncmode", "Sync Mode");

static PRM_Name theTimeDepName("timedep", "Time Dependent");

static PRM_Name theUpdateActiveLayerName("updateactivelayer", "Copy Updates into Editable Layer");
static PRM_Name theAbsAssetPathsName("absassetpaths", "Make Absolute Asset Paths");

static bool fileExists(const char* fileUrl)
{
    PathInfoResult statResult;
    return Client::stat(fileUrl, statResult);
}

static std::string makeRelativeUrl(const char* baseUrl, const char* otherUrl)
{
    StringResult relativeUrl;
    Client::makeRelativeUrl(baseUrl, otherUrl, relativeUrl);
    return relativeUrl.val;
}

static bool is_live_edit_break(SdfLayerHandle layer)
{
    if (!layer->HasCustomLayerData())
    {
        return false;
    }
    pxr::VtDictionary custom_layer_data = layer->GetCustomLayerData();
    pxr::VtDictionary::const_iterator iter = custom_layer_data.find("homni");
    if (iter != custom_layer_data.end())
    {
        pxr::VtDictionary homni_dict = iter->second.Get<pxr::VtDictionary>();
        pxr::VtDictionary::const_iterator break_entry = homni_dict.find("liveEditBreak");
        if (break_entry != homni_dict.end() && break_entry->second.IsHolding<bool>())
        {
            return break_entry->second.UncheckedGet<bool>();
        }
    }

    return false;
}

// Logic based on HUSD_EditLayers::addLayerFromSource() implementation.
static bool update_active_layer(HUSD_AutoWriteLock& lock, pxr::SdfLayerRefPtr src_layer)
{
    auto outdata = lock.data();
    bool success = false;

    if (outdata && outdata->isStageValid())
    {
        if (outdata->addLayer())
        {
            SdfLayerRefPtr layer = outdata->activeLayer();
            SdfLayerRefPtr tmplayer = SdfLayer::CreateAnonymous();

            tmplayer->TransferContent(layer);
            layer->TransferContent(src_layer);

            SdfPath infopath(HUSD_Constants::getHoudiniLayerInfoPrimPath().toStdString());
            success = SdfCopySpec(tmplayer, infopath, layer, infopath);
        }
    }

    return success;
}

bool fix_relative_asset_paths(const VtValue& val, VtValue& out_val, SdfLayerRefPtr anchor_layer)
{
    if (val.IsHolding<SdfAssetPath>())
    {
        auto assetPath = val.UncheckedGet<SdfAssetPath>();
        std::string rawAssetPath = assetPath.GetAssetPath();

        // Handle only relative paths that could not be resolved.
        if (!rawAssetPath.empty() && assetPath.GetResolvedPath().empty())
        {
            std::string absPath = anchor_layer->ComputeAbsolutePath(rawAssetPath);
            if (!absPath.empty())
            {
                out_val = VtValue(SdfAssetPath(absPath));
                return true;
            }
        }
    }
    else if (val.IsHolding<VtArray<SdfAssetPath>>())
    {
        VtArray<SdfAssetPath> updatedVal;
        bool updated_rel_path = false;
        for (const SdfAssetPath& assetPath : val.UncheckedGet<VtArray<SdfAssetPath>>())
        {
            std::string rawAssetPath = assetPath.GetAssetPath();
            if (!rawAssetPath.empty() && assetPath.GetResolvedPath().empty())
            {
                std::string absPath = anchor_layer->ComputeAbsolutePath(rawAssetPath);
                if (!absPath.empty())
                {
                    updatedVal.push_back(SdfAssetPath(absPath));
                    updated_rel_path = true;
                }
                else
                {
                    updatedVal.push_back(assetPath);
                }
            }
            else
            {
                // Retain empty and non-relative paths in the array.
                updatedVal.push_back(assetPath);
            }
        }

        if (updated_rel_path)
        {
            out_val = VtValue(updatedVal);
            return true;
        }
    }

    return false;
}

// Convert relative paths in asset properties in layar
// to absolute paths relative to the anchor_layer path.
// Code based on pxr::UsdUtilsModifyAssetPaths() implementation.
static void fix_relative_asset_paths(SdfLayerRefPtr layer, SdfLayerRefPtr anchor_layer)
{
    if (!(layer && anchor_layer))
    {
        return;
    }

    std::stack<SdfPrimSpecHandle> dfs;
    dfs.push(layer->GetPseudoRoot());

    while (!dfs.empty())
    {
        SdfPrimSpecHandle curr = dfs.top();
        dfs.pop();

        const VtValue propertyNames = curr->GetField(SdfChildrenKeys->PropertyChildren);

        if (propertyNames.IsHolding<std::vector<TfToken>>())
        {
            for (const auto& name : propertyNames.UncheckedGet<std::vector<TfToken>>())
            {
                // For every property
                // Build an SdfPath to the property
                const SdfPath path = curr->GetPath().AppendProperty(name);

                // Check property existence
                const VtValue vtTypeName = layer->GetField(path, SdfFieldKeys->TypeName);
                if (!vtTypeName.IsHolding<TfToken>())
                    continue;

                const TfToken typeName = vtTypeName.UncheckedGet<TfToken>();
                if (typeName == SdfValueTypeNames->Asset || typeName == SdfValueTypeNames->AssetArray)
                {

                    // Check default value
                    VtValue defValue = layer->GetField(path, SdfFieldKeys->Default);

                    VtValue updatedDefValue;
                    if (fix_relative_asset_paths(defValue, updatedDefValue, anchor_layer))
                    {
                        layer->SetField(path, SdfFieldKeys->Default, updatedDefValue);
                    }

                    // Check timeSample values
                    for (double t : layer->ListTimeSamplesForPath(path))
                    {
                        VtValue timeSampleVal;
                        if (layer->QueryTimeSample(path, t, &timeSampleVal))
                        {
                            VtValue updatedTimeSampleVal;
                            if (fix_relative_asset_paths(timeSampleVal, updatedTimeSampleVal, anchor_layer))
                            {
                                layer->SetTimeSample(path, t, updatedTimeSampleVal);
                            }
                        }
                    }
                }
            }
        }

        // children
        for (const SdfPrimSpecHandle& child : curr->GetNameChildren())
        {
            dfs.push(child);
        }
    }
}


PRM_Template LOP_OmniLiveSync::myTemplateList[] = {
    PRM_Template(PRM_ORD, 1, &theSyncModeName, PRMzeroDefaults, &theSyncModeMenu),
    PRM_Template(PRM_TOGGLE, 1, &theTimeDepName),
    PRM_Template(PRM_FILE, 1, &theLiveFileName),
    PRM_Template(PRM_TOGGLE, 1, &theUpdateActiveLayerName, PRMoneDefaults),
    PRM_Template(PRM_TOGGLE, 1, &theAbsAssetPathsName, PRMoneDefaults),
    PRM_Template(PRM_FILE, 1, &theUsdFileName),
    PRM_Template(PRM_CALLBACK, 1, &theCreateLiveLayerName, 0, 0, 0, &LOP_OmniLiveSync::onCreateLiveLayer),
    PRM_Template(PRM_CALLBACK, 1, &theSaveLiveLayerName, 0, 0, 0, &LOP_OmniLiveSync::onSaveLiveLayer),
    PRM_Template(PRM_CALLBACK, 1, &theClearLiveLayerName, 0, 0, 0, &LOP_OmniLiveSync::onClearLiveLayer),
    PRM_Template(PRM_CALLBACK, 1, &theReloadLiveLayerName, 0, 0, 0, &LOP_OmniLiveSync::onReload),
    PRM_Template(PRM_CALLBACK, 1, &theLiveSyncName, 0, 0, 0, &LOP_OmniLiveSync::onLiveSync),
    PRM_Template(),
};

bool LOP_OmniLiveSync::updateParmsFlags()
{
    fpreal t = CHgetEvalTime();
    bool changed = LOP_Node::updateParmsFlags();

    bool pushing = SYNCMODE(t) == 0;
    changed |= enableParm(theTimeDepName.getToken(), !pushing);
    changed |= enableParm(theUsdFileName.getToken(), pushing);
    changed |= enableParm(theCreateLiveLayerName.getToken(), pushing);
    changed |= enableParm(theSaveLiveLayerName.getToken(), pushing);
    changed |= enableParm(theClearLiveLayerName.getToken(), pushing);
    bool abs_paths_enabled = !pushing && UPDATEACTIVELAYER(t);
    changed |= enableParm(theAbsAssetPathsName.getToken(), abs_paths_enabled);
    changed |= enableParm(theUpdateActiveLayerName.getToken(), !pushing);
    return changed;
}

bool LOP_OmniLiveSync::merge_to_live_layer(UsdStageRefPtr input_stage, const std::string& usd_path)
{
    // Merge the input stage anonymous layer deltas to the live layer
    // stage.
    UsdStageRefPtr flattenStage = UsdStage::CreateInMemory();

    SdfLayerHandleVector layer_stack = input_stage->GetLayerStack(false);
    SdfLayerHandle root_layer = input_stage->GetRootLayer();

    // For now, just merge the stack of anonymous layers until we
    // enounter a live edit break layer or the first layer which
    // isn't anonymous.
    bool found_live_edit_break = false;
    for (SdfLayerHandle layer : layer_stack)
    {
        std::string layer_ident = layer->GetIdentifier();
        if (layer_ident == root_layer->GetIdentifier())
        {
            continue;
        }

        if (is_live_edit_break(layer))
        {
            found_live_edit_break = true;
            break;
        }

        if (!layer->IsAnonymous())
        {
            break;
        }

        flattenStage->GetRootLayer()->InsertSubLayerPath(layer_ident);
    }

    if (!found_live_edit_break)
    {
        LOP_Node::addWarning(LOP_MESSAGE, "For efficiency, please use the Omniverse Live Edit Break node to delimit live edit operations.");
    }

    SdfLayerRefPtr flattenedLayer = pxr::UsdUtilsFlattenLayerStack(flattenStage,
                                                                   [&](const PXR_NS::SdfLayerHandle& layer, const std::string& assetPath) {
                                                                       // Files like `OmniPBR.mdl` are effectively search paths, unless they actually
                                                                       // exist, so don't modify them
                                                                       const std::string& assetAbsolutePath = layer->ComputeAbsolutePath(assetPath);
                                                                       if (!fileExists(assetAbsolutePath.c_str()))
                                                                       {
                                                                           return assetPath;
                                                                       }

                                                                       if (usd_path.empty())
                                                                       {
                                                                           return assetPath;
                                                                       }

                                                                       // Make this path relative to the USD.
                                                                       return makeRelativeUrl(usd_path.c_str(), assetAbsolutePath.c_str());
                                                                   });

    // Consideration: Is using SdfCopySpec efficient for live edit updates?
    // Also, investigate why calling live_layer_->TransferContent(flattenedLayer) appears to
    // successfully update the contents of the live layer, but it doesn't trigger a live update.
    SdfCopySpec(flattenedLayer, SdfPath::AbsoluteRootPath(), live_layer_, SdfPath::AbsoluteRootPath());

    return true;
}

int LOP_OmniLiveSync::onCreateLiveLayer(void* data, int index, fpreal t, const PRM_Template* tplate)
{
    LOP_OmniLiveSync* lop = static_cast<LOP_OmniLiveSync*>(data);
    if (!lop->getHardLock()) // only allow saving if we're not locked
    {
        UT_String live_path;
        lop->LIVEPATH(live_path, t);
        if (live_path.length())
        {
            lop->ensureOpenLiveLayer(live_path.c_str());
        }
    }
    return 1;
}

int LOP_OmniLiveSync::onSaveLiveLayer(void* data, int index, fpreal t, const PRM_Template* tplate)
{
    LOP_OmniLiveSync* lop = static_cast<LOP_OmniLiveSync*>(data);
    if (!lop->getHardLock()) // only allow saving if we're not locked
    {
        lop->saveLiveLayer();
    }
    return 1;
}

int LOP_OmniLiveSync::onClearLiveLayer(void* data, int index, fpreal t, const PRM_Template* tplate)
{
    LOP_OmniLiveSync* lop = static_cast<LOP_OmniLiveSync*>(data);
    if (!lop->getHardLock()) // only allow clearing if we're not locked
    {
        lop->clearLiveLayer();
    }
    return 1;
}

int LOP_OmniLiveSync::onReload(void* data, int index, fpreal t, const PRM_Template* tplate)
{
    LOP_OmniLiveSync* lop = static_cast<LOP_OmniLiveSync*>(data);
    if (!lop->getHardLock()) // only allow reloading if we're not locked
    {
        lop->reloadLiveLayer();
        lop->forceRecook();
    }
    return 1;
}

int LOP_OmniLiveSync::onLiveSync(void* data, int index, fpreal t, const PRM_Template* tplate)
{
    LOP_OmniLiveSync* lop = static_cast<LOP_OmniLiveSync*>(data);
    if (!lop->getHardLock()) // only allow reloading if we're not locked
    {
        lop->forceRecook();
    }
    return 1;
}

OP_Node* LOP_OmniLiveSync::myConstructor(OP_Network* net, const char* name, OP_Operator* op)
{
    return new LOP_OmniLiveSync(net, name, op);
}

LOP_OmniLiveSync::LOP_OmniLiveSync(OP_Network* net, const char* name, OP_Operator* op) : LOP_Node(net, name, op)
{
}

LOP_OmniLiveSync::~LOP_OmniLiveSync()
{
}

int LOP_OmniLiveSync::SYNCMODE(fpreal t)
{
    return evalInt(theSyncModeName.getToken(), 0, t);
}

int LOP_OmniLiveSync::TIMEDEP(fpreal t)
{
    return evalInt(theTimeDepName.getToken(), 0, t);
}

void LOP_OmniLiveSync::LIVEPATH(UT_String& str, fpreal t)
{
    evalString(str, theLiveFileName.getToken(), 0, t);
}

void LOP_OmniLiveSync::USDPATH(UT_String& str, fpreal t)
{
    evalString(str, theUsdFileName.getToken(), 0, t);
}

int LOP_OmniLiveSync::ABSASSETPATHS(fpreal t)
{
    return evalInt(theAbsAssetPathsName.getToken(), 0, t);
}

int LOP_OmniLiveSync::UPDATEACTIVELAYER(fpreal t)
{
    return evalInt(theUpdateActiveLayerName.getToken(), 0, t);
}

OP_ERROR
LOP_OmniLiveSync::cookMyLop(OP_Context& context)
{
    fpreal time = context.getTime();
    bool pushing = SYNCMODE(time) == 0;

    // Node can only be time dependent when pulling
    flags().setTimeDep(!pushing && TIMEDEP(time));

    return pushing ? pushLiveSync(context) : pullLiveSync(context);
}

OP_ERROR
LOP_OmniLiveSync::pullLiveSync(OP_Context& context)
{
    homni::Client::usdLiveProcess();

    // Cook the node connected to our input, and make a "soft copy" of the
    // result into our own HUSD_DataHandle.
    if (cookModifyInput(context) >= UT_ERROR_FATAL)
        return error();

    float time = context.getTime();
    UT_String live_path;
    LIVEPATH(live_path, time);

    if (!live_path.length())
    {
        LOP_Node::addWarning(LOP_MESSAGE, "A Live File path must be provide for live editing.");
        return error();
    }

    // Use editableDataHandle to get non-const access to our data handle, and
    // the lock it for writing. This makes sure that the USD stage is set up
    // to match the configuration defined in our data handle. Any edits made
    // to the stage at this point will be preserved in our data handle when
    // we unlock it.
    HUSD_AutoWriteLock writelock(editableDataHandle());
    HUSD_AutoLayerLock layerlock(writelock);

    ensureOpenLiveLayer(live_path.c_str());
    if (!live_layer_)
    {
        return error();
    }

    XUSD_DataPtr data = writelock.data();

    if (!data)
    {
        return error();
    }

    if (UPDATEACTIVELAYER(time))
    {
        // Copy the live layer into the anonymous active layer.
        if (!update_active_layer(writelock, live_layer_))
        {
            LOP_Node::addWarning(LOP_MESSAGE, "Couldn't add live layer to node data.");
            return error();
        }
        if (ABSASSETPATHS(time))
        {
            fix_relative_asset_paths(data->activeLayer(), live_layer_);
        }
    }
    else
    {
        // Add the live file layer.
        if (!data->addLayer(live_path.c_str(), SdfLayerOffset(), 0, XUSD_AddLayerOp::XUSD_ADD_LAYERS_ALL_LOCKED, false))
        {
            LOP_Node::addWarning(LOP_MESSAGE, "Couldn't add live layer to node data.");
        }
    }

    // Set the last modified prim to the first root prim in the layer that isn't
    // the HoudiniLayerInfo.
    for (pxr::SdfPrimSpecHandle root_prim_spec : live_layer_->GetRootPrims())
    {
        pxr::SdfPath root_path = root_prim_spec->GetPath();
        if (root_path != HUSDgetHoudiniLayerInfoSdfPath())
        {
            setLastModifiedPrims(root_path.GetAsString());
            break;
        }
    }

    return error();
}

OP_ERROR
LOP_OmniLiveSync::pushLiveSync(OP_Context& context)
{
    // Cook the node connected to our input, and make a "soft copy" of the
    // result into our own HUSD_DataHandle.
    if (cookModifyInput(context) >= UT_ERROR_FATAL)
        return error();

    UT_String live_path;
    LIVEPATH(live_path, context.getTime());

    UT_String usd_path;
    USDPATH(usd_path, context.getTime());

    if (!live_path.length())
    {
        LOP_Node::addWarning(LOP_MESSAGE, "A Live File path must be provided for live editing.");
        return error();
    }

    const HUSD_DataHandle& data_handle = lockedInputData(context, 0);
    HUSD_AutoReadLock readlock(data_handle);

    UsdStageRefPtr input_stage = readlock.data()->stage();

    if (!input_stage)
    {
        LOP_Node::addError(LOP_FAILED_TO_COOK, "Couldn't get input stage.");
        return error();
    }

    ensureOpenLiveLayer(live_path.c_str());
    if (!live_layer_)
    {
        return error();
    }

    merge_to_live_layer(input_stage, usd_path.c_str());

    homni::Client::usdLiveProcess();

    return error();
}

void LOP_OmniLiveSync::releaseLiveLayer()
{
    if (live_layer_)
    {
        live_layer_.Reset();
    }
}

void LOP_OmniLiveSync::clearLiveLayer()
{
    if (live_layer_)
    {
        live_layer_->Clear();
    }
}

void LOP_OmniLiveSync::ensureOpenLiveLayer(const std::string& live_path)
{
    if (live_path.empty())
    {
        releaseLiveLayer();
        return;
    }

    if (live_layer_ && live_layer_->GetIdentifier() == live_path)
    {
        return;
    }

    live_layer_ = SdfLayer::FindOrOpen(live_path);
    if (!live_layer_)
    {
        live_layer_ = SdfLayer::CreateNew(live_path);
    }

    if (!live_layer_)
    {
        LOP_Node::addError(LOP_FAILED_TO_COOK, "Couldn't create live layer.");
        return;
    }
}

void LOP_OmniLiveSync::saveLiveLayer()
{
    if (live_layer_)
    {
        if (!live_layer_->Save(true))
        {
            LOP_Node::addWarning(LOP_MESSAGE, "Saving live layer failed.");
        }
    }
}

void LOP_OmniLiveSync::reloadLiveLayer()
{
    if (live_layer_)
    {
        live_layer_->Reload();
    }
}
