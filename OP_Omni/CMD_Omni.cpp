// SPDX-FileCopyrightText: Copyright (c) 2019-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: LicenseRef-NvidiaProprietary
//
// NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
// property and proprietary rights in and to this material, related
// documentation and any modifications thereto. Any use, reproduction,
// disclosure or distribution of this material and related documentation
// without an express license agreement from NVIDIA CORPORATION or
// its affiliates is strictly prohibited.

#include "HoudiniOmni.h"
#include "HoudiniOmniResultTypes.h"
#include "HoudiniOmniUtils.h"

#include <CMD/CMD_Args.h>
#include <CMD/CMD_Manager.h>
#include <UT/UT_DSOVersion.h>
#include <math.h>
#include <string.h>

using namespace std;
using namespace homni;

namespace
{

void omniInitialize(CMD_Args& args)
{
    bool success = Client::initialize();

    args.out() << "Omniverse client initialization " << (success ? "successful" : "failed") << endl;
}

void omniShutdown(CMD_Args& args)
{
    Client::shutDown();
}

void omniList(CMD_Args& args)
{
    if (args.argc() < 2)
    {
        args.err() << "Usage: omni_list [-v (verbose listing)] [-e (print errors)] <omniverse_url> " << endl;
        return;
    }

    const char* path = args.argv(1);

    bool verbose = args.found('v');

    bool printErrors = args.found('e');

    PathInfoResultVector list;
    StatusResult err;

    if (!Client::listPaths(path, list, &err))
    {
        if (printErrors)
        {
            args.err() << "Listing " << path << " failed.";
            if (!err.description.empty())
            {
                args.err() << err.description;
            }

            args.err() << endl;
        }

        return;
    }

    for (const PathInfoEntry& entry : list.items)
    {
        args.out() << entry.path << endl;

        if (verbose)
        {
            args.out() << "    type: " << entry.info.pathType << " size: " << entry.info.size << " version: '" << entry.version << "'" << endl;
        }
    }
}

void omniStat(CMD_Args& args)
{
    if (args.argc() < 2)
    {
        args.err() << "Usage: omni_stat <omniverse_url> " << endl;
        return;
    }

    const char* path = args.argv(1);

    PathInfoResult statResult;
    StatusResult err;

    if (!Client::stat(path, statResult, &err))
    {
        args.err() << "stat " << path << " failed.\n";
        if (!err.description.empty())
        {
            args.err() << err.description;
            args.err() << endl;
        }

        return;
    }


    args.out() << path << endl;
    args.out() << "    type: " << statResult.entry.info.pathType << " size: " << statResult.entry.info.size << " version: '"
               << statResult.entry.version << "'" << endl;
}

void omniListConnections(CMD_Args& args)
{
    StringResultVector resultVec;

    Client::listConnections(resultVec);

    for (const std::string& conn : resultVec.items)
    {
        args.out() << conn << endl;
    }
}

void omniCacheDir(CMD_Args& args)
{
    args.out() << "Omniverse cache diretory: '" << Client::getCacheDir() << "'" << endl;
}

void omniDownload(CMD_Args& args)
{
    if (args.argc() < 2)
    {
        args.err() << "Usage: [-v (verbose)] omni_dowmnload <omni_uri_path>" << endl;
        return;
    }

    const char* omniPath = args.argv(1);

    bool verbose = args.found('v');

    StatusResult err;

    StringResult cacheFilePath;
    StringResult version;

    if (Client::downloadContentToCache(omniPath, &cacheFilePath, &err, nullptr, &version))
    {
        if (verbose)
        {
            args.out() << "Downloaded '" << omniPath << "' version " << version.val << "\n    to cache path '" << cacheFilePath.val << endl;
        }
    }
    else
    {
        args.err() << "Download failed.";
        if (!err.description.empty())
        {
            args.err() << err.description;
        }

        args.err() << endl;
    }
}


void omniUpload(CMD_Args& args)
{
    if (args.argc() < 2)
    {
        args.err() << "Usage: [-v (verbose)] omni_upload <server_path>" << endl;
        return;
    }

    const char* serverPath = args.argv(1);

    bool verbose = args.found('v');

    StatusResult err;

    if (Client::uploadContentFromCache(serverPath, &err))
    {
        if (verbose)
        {
            args.out() << "Uploaded to serever path '" << serverPath << endl;
        }
    }
    else
    {
        args.err() << "Upload failed.";
        if (!err.description.empty())
        {
            args.err() << " Error: " << err.description;
        }

        args.err() << endl;
    }
}

void omniDelete(CMD_Args& args)
{
    if (args.argc() < 2)
    {
        args.err() << "Usage: omni_delete <omni_uri>" << endl;
        return;
    }

    const char* serverPath = args.argv(1);

    Client::deleteFile(serverPath);
}

void omniUsdLiveProcess(CMD_Args& args)
{
    Client::usdLiveProcess();
}

void omniServerPath(CMD_Args& args)
{
    if (args.argc() < 2)
    {
        args.err() << "Usage: omni_server_path <omni_uri_path>" << endl;
        return;
    }

    const char* uriPath = args.argv(1);
    std::string serverPath;
    OmniUtils::getRelativeServerPath(uriPath, serverPath);

    if (!serverPath.empty())
    {
        args.out() << serverPath << endl;
    }
}

void omniAddBookmark(CMD_Args& args)
{
    if (args.argc() < 2)
    {
        args.err() << "Usage: omni_add_bookmark <host_name>" << endl;
        return;
    }

    std::string pathPrefix("omniverse://");


    pathPrefix += std::string(args.argv(1));


    UTaddAbsolutePathPrefix(pathPrefix.c_str());
}


} // End anonymous namespace


void CMDextendLibrary(CMD_Manager* cman)
{
    cman->installCommand("omni_initialize", "", omniInitialize);
    cman->installCommand("omni_add_bookmark", "", omniAddBookmark);
    cman->installCommand("omni_shutdown", "", omniShutdown);
    cman->installCommand("omni_list", "ve", omniList);
    cman->installCommand("omni_stat", "", omniStat);
    cman->installCommand("omni_list_connections", "", omniListConnections);
    cman->installCommand("omni_cache_dir", "", omniCacheDir);
    cman->installCommand("omni_download", "v", omniDownload);
    cman->installCommand("omni_upload", "v", omniUpload);
    cman->installCommand("omni_delete", "s:", omniDelete);
    cman->installCommand("omni_usd_live_process", "", omniUsdLiveProcess);
    cman->installCommand("omni_server_path", "", omniServerPath);
}
