// SPDX-FileCopyrightText: Copyright (c) 2021-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: LicenseRef-NvidiaProprietary
//
// NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
// property and proprietary rights in and to this material, related
// documentation and any modifications thereto. Any use, reproduction,
// disclosure or distribution of this material and related documentation
// without an express license agreement from NVIDIA CORPORATION or
// its affiliates is strictly prohibited.

#pragma once

#include <LOP/LOP_Node.h>
#include <pxr/usd/sdf/layer.h>
#include <pxr/usd/usd/stage.h>

namespace homni
{

class LOP_OmniLiveSync : public LOP_Node
{
public:
    LOP_OmniLiveSync(OP_Network* net, const char* name, OP_Operator* op);

    ~LOP_OmniLiveSync() override;

    static PRM_Template myTemplateList[];
    static OP_Node* myConstructor(OP_Network* net, const char* name, OP_Operator* op);

protected:
    // Method to cook USD data for the LOP
    OP_ERROR cookMyLop(OP_Context& context) override;

    bool updateParmsFlags() override;

private:
    OP_ERROR pullLiveSync(OP_Context& context);
    OP_ERROR pushLiveSync(OP_Context& context);

    void ensureOpenLiveLayer(const std::string& live_layer_path);
    void saveLiveLayer();
    void reloadLiveLayer();

    int SYNCMODE(fpreal t);
    int TIMEDEP(fpreal t);
    void LIVEPATH(UT_String& str, fpreal t);
    void USDPATH(UT_String& str, fpreal t);
    int ABSASSETPATHS(fpreal t);
    int UPDATEACTIVELAYER(fpreal t);

    void releaseLiveLayer();
    void clearLiveLayer();

    static int onCreateLiveLayer(void* data, int index, fpreal t, const PRM_Template* tplate);

    static int onSaveLiveLayer(void* data, int index, fpreal t, const PRM_Template* tplate);

    static int onClearLiveLayer(void* data, int index, fpreal t, const PRM_Template* tplate);

    static int onReload(void* data, int index, fpreal t, const PRM_Template* tplate);

    static int onLiveSync(void* data, int index, fpreal t, const PRM_Template* tplate);

    bool merge_to_live_layer(pxr::UsdStageRefPtr input_stage, const std::string& usd_path);

    pxr::SdfLayerRefPtr live_layer_;
};

} // namespace homni
