// SPDX-FileCopyrightText: Copyright (c) 2020-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: LicenseRef-NvidiaProprietary
//
// NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
// property and proprietary rights in and to this material, related
// documentation and any modifications thereto. Any use, reproduction,
// disclosure or distribution of this material and related documentation
// without an express license agreement from NVIDIA CORPORATION or
// its affiliates is strictly prohibited.

#pragma once

// The following is automatically created when generating the project
// with cmake (see the generate_export_header() cmake function).
#include "HoudiniOmniTypes.h"
#include "houdiniomni_export.h"

#include <string>
#include <vector>

namespace homni
{

struct StringResultVector : public ClientStringResultContainer
{
    void insert(const char* val) override
    {
        const char* strVal = val ? val : "";
        items.push_back(strVal);
    }

    std::vector<std::string> items;
};

struct StringResult : public ClientStringResult
{
    void set(const char* inVal) override
    {
        if (inVal)
        {
            val = inVal;
        }
    }

    std::string val;
};


struct StatusResult : public ClientStatusResult
{
public:
    virtual void set(uint64_t inStatus, const char* inDescription) override
    {
        status = inStatus;
        if (inDescription)
        {
            description = inDescription;
        }
    }

    uint64_t status = 0;
    std::string description;
};


struct PathInfoEntry
{
    std::string path;
    PathInfo info;
    std::string version;
};


struct PathInfoResult : public ClientPathResult
{
    void set(const char* inPath, const PathInfo& inInfo, const char* inVersion) override
    {
        entry.info = inInfo;

        if (inPath)
        {
            entry.path = inPath;
        }

        if (inVersion)
        {
            entry.version = inVersion;
        }
    }

    PathInfoEntry entry;
};


struct PathInfoResultVector : public ClientPathResultContainer
{
    void insert(const char* inPath, const PathInfo& inInfo, const char* inVersion) override
    {
        PathInfoEntry entry;
        entry.info = inInfo;

        if (inPath)
        {
            entry.path = inPath;
        }

        if (inVersion)
        {
            entry.version = inVersion;
        }

        items.push_back(entry);
    }

    std::vector<PathInfoEntry> items;
};

struct PathStringResultVector : public ClientPathResultContainer
{
    void insert(const char* inPath, const PathInfo& inInfo, const char* inVersion) override
    {
        if (inPath)
        {
            items.push_back(std::string(inPath));
        }
    }

    std::vector<std::string> items;
};

} // namespace homni
