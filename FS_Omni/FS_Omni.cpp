// SPDX-FileCopyrightText: Copyright (c) 2019-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: LicenseRef-NvidiaProprietary
//
// NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
// property and proprietary rights in and to this material, related
// documentation and any modifications thereto. Any use, reproduction,
// disclosure or distribution of this material and related documentation
// without an express license agreement from NVIDIA CORPORATION or
// its affiliates is strictly prohibited.

#include "FS_Omni.h"

#include "FS_OmniInfoHelper.h"
#include "FS_OmniReadHelper.h"
#include "FS_OmniWriteHelper.h"

#include <OP/OP_Director.h>
#include <UT/UT_DSOVersion.h>
#include <chrono>
#include <ctime>
#include <filesystem>
#include <unordered_map>

using namespace std;
using namespace ::std::chrono;

namespace fs = std::filesystem;

void installFSHelpers()
{
    new homni::FS_OmniReadHelper();
    new homni::FS_OmniWriteHelper();
    new homni::FS_OmniInfoHelper();
}

namespace
{

// Utility:  Adds a filesystem absolute path prefix
// for an Omniverse URL for the given server.
void addAbsoluteOmniversePrefix(const std::string& server)
{
    if (!server.empty() && !std::all_of(server.begin(), server.end(), [](unsigned char c) {
            return std::isspace(c);
        }))
    {
        std::string pathPrefix("omniverse://");
        pathPrefix += server;
        UTaddAbsolutePathPrefix(pathPrefix.c_str());
    }
}

} // End anonymous namespace

namespace homni
{

void FS_Omni::addAbsolutePathPrefixes()
{
    UTaddAbsolutePathPrefix(OmniUtils::omniSignature());

    UTaddAbsolutePathPrefix(OmniUtils::omniverseFileSystemPrefix());

    std::string bookmarks = OmniUtils::getEnvVar("HOMNI_DEFAULT_CONNECTIONS");

    if (!bookmarks.empty())
    {
        // Split bookmarks on ';' delimiter.
        while (true)
        {
            string server;

            size_t semiIdx = bookmarks.find(';');

            if (semiIdx == std::string::npos)
            {
                server = bookmarks;
            }
            else
            {
                server = bookmarks.substr(0, semiIdx);
                if (semiIdx < bookmarks.size() - 1)
                {
                    bookmarks = bookmarks.substr(semiIdx + 1);
                }
                else
                {
                    bookmarks.clear();
                }
            }

            addAbsoluteOmniversePrefix(server);

            if (semiIdx == std::string::npos || bookmarks.empty())
            {
                break;
            }
        }
    }
}

void FS_Omni::flagError(const char* msg)
{
    if (!msg)
    {
        return;
    }

    OP_Node* node = OPgetDirector()->getCwd();

    if (node)
    {
        node->opLocalError(OP_ERR_ANYTHING, msg);
    }
}


bool FS_Omni::getOmniDirContents(const char* source, PathInfoResultVector& outPaths)
{
    string path(source);

    if (path.empty())
    {
        return false;
    }

    normalizePath(path);

    StringResult serverPath;
    StringResult host;
    StringResult user;
    StringResult port;

    if (!Client::parseOmniPath(path.c_str(), serverPath, host, user, port))
    {
        return false;
    }
    // If there is no host provide, return false directly, no need to check Client::listPaths
    if (host.val.empty())
    {
        return false;
    }

    return Client::listPaths(path.c_str(), outPaths);
}


void FS_Omni::setModifiedTime(const char* diskPath, uint64_t modifiedTimeSec)
{
    fs::path p(diskPath);

    if (!fs::exists(p))
    {
        return;
    }

    std::chrono::seconds sec(modifiedTimeSec);
    fs::file_time_type::duration dur(sec);
    fs::file_time_type updateTime(dur);
    fs::last_write_time(p, updateTime);
}

} // namespace homni
