// SPDX-FileCopyrightText: Copyright (c) 2019-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: LicenseRef-NvidiaProprietary
//
// NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
// property and proprietary rights in and to this material, related
// documentation and any modifications thereto. Any use, reproduction,
// disclosure or distribution of this material and related documentation
// without an express license agreement from NVIDIA CORPORATION or
// its affiliates is strictly prohibited.

#include "FS_OmniInfoHelper.h"

#include "FS_Omni.h"
#include "HoudiniOmni.h"

#include <map>


using namespace std;

namespace homni
{

FS_OmniInfoHelper::FS_OmniInfoHelper()
{
    FS_Omni::addAbsolutePathPrefixes();
}

FS_OmniInfoHelper::~FS_OmniInfoHelper()
{
}

bool FS_OmniInfoHelper::canHandle(const char* source)
{
    return (OmniUtils::isOmniversePath(source) && isPathValid(source));
}

bool FS_OmniInfoHelper::isPathValid(const char* source)
{
    string path(source);

    if (path.empty())
    {
        return false;
    }

    FS_Omni::normalizePath(path);

    StringResult serverPath;
    StringResult host;
    StringResult user;
    StringResult port;

    if (!Client::parseOmniPath(path.c_str(), serverPath, host, user, port))
    {
        return false;
    }

    // There is no host provide
    if (host.val.empty())
    {
        return false;
    }
    return true;
}

bool FS_OmniInfoHelper::hasAccess(const char* source, int mode)
{
    if (!canHandle(source))
    {
        return false;
    }

    // Consideration:  Verify that the logic below is correct and how mode should
    // be intepreted.  If mode is not zero, I'm assuming we should return
    // true if any of the conditions specified by this flag are true.  I.e.,
    // if the mode is 3 (FS_READ | FS_WRITE), we return true if the file
    // has either read or write access.  From my tests, mode is set by
    // Houdini only to the values 0 or 7 when navigating with the file
    // browser.  I have yet to see a case where hasAccess() is invoked with
    // mode set to 1 or 2, for example.  It's also not clear how to determine
    // write permissions if the file doesn't exist, e.g., should we check
    // the write permissions of the parent folder in that case?
    // For now, we always return false if the file doesn't exist.

    string path(source);
    FS_Omni::normalizePath(path);

    PathInfoResult statResult;

    if (!Client::stat(path.c_str(), statResult))
    {
        return false;
    }

    uint32_t access = statResult.entry.info.access;

    bool hasAccess = (mode == 0 || (mode & FS_FileAccessMode::FS_READ && access & homni::PathAccessType::PathAccess_Read) ||
                      (mode & FS_FileAccessMode::FS_WRITE && access & homni::PathAccessType::PathAccess_Write));

    return hasAccess;
}

bool FS_OmniInfoHelper::getIsDirectory(const char* source)
{
    if (!canHandle(source))
    {
        return false;
    }

    string path(source);
    FS_Omni::normalizePath(path);

    PathInfoResult statResult;

    if (!Client::stat(path.c_str(), statResult))
    {
        return false;
    }

    return statResult.entry.info.pathType & homni::PathTypeFlags::PathType_CanHaveChildren;
}

ModTimeType FS_OmniInfoHelper::getModTime(const char* source)
{
    if (!canHandle(source))
    {
        return 0;
    }

    string path(source);
    FS_Omni::normalizePath(path);

    PathInfoResult statResult;

    if (!Client::stat(path.c_str(), statResult))
    {
        return false;
    }

    return statResult.entry.info.modifiedTimestampNs / 1000000000;
}

int64 FS_OmniInfoHelper::getSize(const char* source)
{
    if (!canHandle(source))
    {
        return 0;
    }

    string path(source);
    FS_Omni::normalizePath(path);

    PathInfoResult statResult;

    if (!Client::stat(path.c_str(), statResult))
    {
        return false;
    }

    return statResult.entry.info.size;
}

UT_String FS_OmniInfoHelper::getExtension(const char* source)
{
    return FS_InfoHelper::getExtension(source);
}

bool FS_OmniInfoHelper::getContents(const char* source, UT_StringArray& contents, UT_StringArray* dirs)
{
    if (!canHandle(source))
    {
        return false;
    }

    PathInfoResultVector paths;

    if (!FS_Omni::getOmniDirContents(source, paths))
    {
        return false;
    }

    for (const PathInfoEntry& entry : paths.items)
    {
        std::string name = entry.path;

        // Remove trailing slashes, if any.
        while (!name.empty() && name.back() == '/')
        {
            name.pop_back();
        }

        if (name.empty())
        {
            continue;
        }

        if (entry.info.pathType & homni::PathTypeFlags::PathType_CanHaveChildren && dirs)
        {
            dirs->append(name.c_str());
        }
        else
        {
            contents.append(name.c_str());
        }
    }

    return true;
}

} // namespace homni
