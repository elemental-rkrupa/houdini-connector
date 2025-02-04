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

// The following is automatically created when generating the project
// with cmake (see the generate_export_header() cmake function).
#include "HoudiniOmniTypes.h"
#include "houdiniomni_export.h"

#include <cstdint>
#include <omni/log/ILog.h>


//! The namespace used for omni_connect_core specific settings
static constexpr const char* kConnectorName = "HoudiniConnector";

//! Declares (but does not enable) the main logging channel used by the Houdini Connector
OMNI_LOG_DECLARE_CHANNEL(kHoudiniConnectorChannel);
OMNI_LOG_DECLARE_CHANNEL(kOmniClientChannel);


namespace homni
{

class HOUDINIOMNI_EXPORT Client
{
public:
    static bool initialize();

    static bool connected();

    static void listConnections(ClientStringResultContainer& result);

    static void shutDown();

    static bool listPaths(const char* path, ClientPathResultContainer& result, ClientStatusResult* log = nullptr);

    static bool stat(const char* path, ClientPathResult& result, ClientStatusResult* errLog = nullptr);

    static bool copyFile(const char* srcUrl, const char* dstUrl, bool overWrite, ClientStatusResult* log = nullptr);

    static bool createFolder(const char* ursl, ClientStatusResult* log = nullptr);

    static bool getLocalFile(const char* url, ClientStringResult& ouLocalPath, ClientStatusResult* log = nullptr);

    static bool downloadContent(const char* path, Content& content, ClientStringResult* version = nullptr, ClientStatusResult* log = nullptr);

    static bool downloadContentToCache(const char* omniPath,
                                       ClientStringResult* cacheFilePath = nullptr,
                                       ClientStatusResult* log = nullptr,
                                       Content* outContent = nullptr,
                                       ClientStringResult* version = nullptr,
                                       bool force = false);

    static void freeContent(Content& content);

    static bool uploadContent(const char* path, Content& content, ClientStatusResult* log = nullptr);

    static bool uploadContentFromCache(const char* path, ClientStatusResult* log = nullptr);

    static bool deleteFile(const char* path, ClientStatusResult* log = nullptr);

    static void usdLiveProcess();

    static bool parseOmniPath(const char* omniPath,
                              ClientStringResult& outPath,
                              ClientStringResult& outHost,
                              ClientStringResult& outUser,
                              ClientStringResult& outPort);

    static const char* getCacheDir();

    static const char* getLogFileBaseName();

    // Return the local disk cache path of the given server path, optionally attempting
    // to create the parent directories in the cache.  Returns true if successful
    // and false otherwise.
    static bool getCachePath(const char* serverPath, ClientStringResult& outPath, bool createDirs = true, ClientStatusResult* log = nullptr);

    static void setLogLevel(LogLevel level);

    static LogLevel getLogLevel();

    static void normalizeUrl(const char* inUrl, ClientStringResult& outUrl);

    static void pushBaseUrl(const char* baseUrl);

    static bool popBaseUrl(const char* baseUrl);

    static void signOut(const char* url);

    static void reconnect(const char* url);

    // Number of times the list of open connections has been updated.
    // This value can be used to efficiently monitor the dirty state
    // of the open connections list.
    static int connectionUpdateCount();

    static const char* getVersionString();

    static void makeRelativeUrl(const char* baseUrl, const char* otherUrl, ClientStringResult& outResult);

    static void setCheckpointMessage(const char* msg);
    static void clearCheckpointMessage();
    static const char* getConnectorName();
};

} // namespace homni
