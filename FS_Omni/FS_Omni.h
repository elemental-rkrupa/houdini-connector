// SPDX-FileCopyrightText: Copyright (c) 2019-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: LicenseRef-NvidiaProprietary
//
// NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
// property and proprietary rights in and to this material, related
// documentation and any modifications thereto. Any use, reproduction,
// disclosure or distribution of this material and related documentation
// without an express license agreement from NVIDIA CORPORATION or
// its affiliates is strictly prohibited.

#pragma once

#include "HoudiniOmni.h"
#include "HoudiniOmniResultTypes.h"
#include "HoudiniOmniUtils.h"

#include <FS/FS_Utils.h> // Needed for plugin to load FS definitions.
#include <string>
#include <vector>

namespace homni
{

// Class for omni file system utilities.
class FS_Omni
{
public:
    static void addAbsolutePathPrefixes();

    // Sets an error on the current node.
    static void flagError(const char* msg);

    // Normalize paths with a trailing '..' by attempting to remove the final
    // directory name.  E.g., converts "/Users/test/.." to "/Users".
    static void normalizePath(std::string& path)
    {
        size_t len = path.length();

        if (len > 4 && path.substr(len - 3) == "/..")
        {
            size_t prevSlash = path.rfind('/', len - 4);

            if (prevSlash != std::string::npos)
            {
                path = path.substr(0, prevSlash + 1);
            }
        }
    }

    static bool getOmniDirContents(const char* source, PathInfoResultVector& outPaths);

    // Set the modified of the given file on disk.
    static void setModifiedTime(const char* diskPath, uint64_t modifiedTimeSec);
};

} // namespace homni
