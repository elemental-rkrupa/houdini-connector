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

#include "HoudiniOmniUtils.h"
#include "HoudiniOmniVersion.h"

#include <OmniClient.h>
#include <chrono>
#include <ctime>
#include <filesystem>
#include <fstream>
#include <future>
#include <iostream>
#include <mutex>
#include <omni/core/OmniInit.h>
#include <omni/log/ILog.h>
#include <set>
#include <sstream>
#include <string>
#include <unordered_map>

#if defined(_WIN32) || defined(_WIN64)
#    include <windows.h>
#else
// Consideration: we are assuming the platform is Linux if not Windows.. need better handling
#    define _MAX_PATH 4096
#    define GetShortPathName(longPath, shortPath, _MAX_PATH) return longPath;
#endif

#include <cstring>
#include <stdio.h>
#include <string.h>
#include <vector>

using namespace std;
namespace fs = std::filesystem;

// Initialize the Omniverse application
OMNI_APP_GLOBALS(kConnectorName, "Omniverse Houdini Connector");
OMNI_LOG_ADD_CHANNEL(kHoudiniConnectorChannel, kConnectorName, "Messages from the Houdini Connector");
OMNI_LOG_ADD_CHANNEL(kOmniClientChannel, "OmniClient", "Messages from the OmniClient");

static bool gOmniClientInitialized = false;
static std::set<std::string> gOpenConnections;
static int gOpenConnectionsUpdateCount = 0;
static std::mutex gConnectionsUpdateMutex;
static std::mutex gLogOutputMutex; // Helps prevent interleaved logging output from multiple threads.

static OmniClientLogLevel gOmniClientLogLevel = OmniClientLogLevel::eOmniClientLogLevel_Error;
static homni::LogLevel gHomniLogLevel = homni::LogLevel_Error;
static omni::log::Level gOmniLogLevel = omni::log::Level::eVerbose; // We log everything from omni.log to log file.

static std::string gCheckpointMessage = "";
static std::mutex gCheckpointMessageMutex;

// We need persistent storage to a null-terminated cache path
// c-string we can pass back to the user.
static string gCacheDir;

using namespace homni;

static string getCacheBaseDir()
{
    string result = OmniUtils::getEnvVar("HOME");

    if (result.empty())
    {
        result = OmniUtils::getEnvVar("USERPROFILE");
    }

    if (result.empty())
    {
        string homePath = OmniUtils::getEnvVar("HOMEPATH");
        string homeDrv = OmniUtils::getEnvVar("HOMEDRIVE");

        if (!(homePath.empty() || homeDrv.empty()))
        {
            result = homeDrv + homePath;
        }
    }

    return result;
}


static void initCacheDir()
{
    string cacheDir = getCacheBaseDir();
    cacheDir += "/Omniverse/Houdini/";

    if (cacheDir.size() >= _MAX_PATH)
    {
        OMNI_LOG_ERROR(kHoudiniConnectorChannel, "cacheDir exceeds maximum path length (%d): %s", _MAX_PATH, cacheDir.c_str());
    }
    else
    {
        gCacheDir = cacheDir;
    }
}


namespace
{
class HomniLog
{
    bool m_enabled;
    bool m_initialized;
    std::string m_fileName;
    std::string m_cache;

public:
    static const char* const logFileBaseName()
    {
        return "HoudiniOmniClient.log";
    }

    HomniLog() : m_enabled(true), m_initialized(false)
    {
        string enabledVar = OmniUtils::getEnvVar("HOMNI_ENABLE_LOGFILE");
        if (!enabledVar.empty())
        {
            m_enabled = enabledVar != "0";
        }
    }

    ~HomniLog()
    {
        if (m_enabled)
        {
            log("End Homni Log");
        }
    }

    void init()
    {
        if (!m_enabled)
        {
            return;
        }
        if (gCacheDir.length() == 0)
        {
            initCacheDir();
        }

        fs::path path(gCacheDir);
        path /= "log";
        if (!fs::is_directory(path))
        {
            std::error_code ec;
            fs::create_directories(path, ec);
            if (ec)
            {
                std::cerr << "Initializing logger: error creating cache directory " << path.string() << ". Disabling logging to file." << std::endl;
                m_enabled = false;
                return;
            }
        }

        path /= logFileBaseName();
        m_fileName = path.string();

        FILE* fp = fopen(m_fileName.c_str(), "w");
        if (fp)
        {
            fclose(fp);
        }
    }

    void log(const string& msg)
    {
        if (m_enabled && !msg.empty())
        {
            m_cache += msg;
            flush();
        }
    }

    bool flush()
    {
        if (m_cache.empty())
        {
            return true;
        }

        if (!m_initialized)
        {
            init();
            m_initialized = true;
        }

        if (m_fileName.empty())
        {
            m_cache.clear();
            return false;
        }

        FILE* fp = fopen(m_fileName.c_str(), "a+");
        if (fp)
        {
            fputs(m_cache.c_str(), fp);
            fclose(fp);
            m_cache.clear();
            return true;
        }
        m_cache.clear();
        return false;
    }
};


class FetchedFileEntry
{
public:
    uint64_t modifiedTime;
    string version;
    string cacheFilePath;
    std::mutex mtx;

    FetchedFileEntry() : modifiedTime(0)
    {
    }

    bool isValid(const char* inVersion, uint64_t inModifiedTimeNs) const
    {
        if (cacheFilePath.empty())
        {
            return false;
        }

        bool valid = strcmp(inVersion, version.c_str()) == 0 && modifiedTime == inModifiedTimeNs;

        if (valid)
        {
            // Check if file exists.
            fs::path p(cacheFilePath);
            valid = fs::exists(p);

            if (valid)
            {
                // Check that file modified time matches.
                std::chrono::seconds sec(inModifiedTimeNs / 1000000000);
                fs::file_time_type::duration dur(sec);
                fs::file_time_type inModifiedTime(dur);

                valid = fs::last_write_time(p) == inModifiedTime;
            }
        }

        return valid;
    }
};

class FetchedFileMap
{
public:
    FetchedFileMap()
    {
    }

    ~FetchedFileMap()
    {
        for (std::pair<std::string, FetchedFileEntry*> item : m_fetchedItems)
        {
            // Remove the temporary file.
            if (!item.second->cacheFilePath.empty())
            {
                remove(item.second->cacheFilePath.c_str());
            }
            delete item.second;
        }
    }

    FetchedFileEntry* getItem(const char* url)
    {
        std::unique_lock<std::mutex> mapAccessLock(m_mutex);

        unordered_map<string, FetchedFileEntry*>::iterator it = m_fetchedItems.find(url);

        if (it != m_fetchedItems.end())
        {
            return it->second;
        }

        FetchedFileEntry* newEntry = new FetchedFileEntry();

        m_fetchedItems.insert(make_pair(string(url), newEntry));

        return newEntry;
    }

    FetchedFileMap& operator=(const FetchedFileMap&) = delete;
    FetchedFileMap(const FetchedFileMap&) = delete;

private:
    // NB: We should eventually use a concurrent map for effieciency,
    // but can keep the implementation simple initially.
    // For now, we don't clear this map for the lifetime of the application.
    std::unordered_map<string, FetchedFileEntry*> m_fetchedItems;
    std::mutex m_mutex;
};
} // namespace

static FetchedFileMap gFetchMap;
static HomniLog gLog;


static void initDefaults()
{
    std::string logLevel = OmniUtils::getEnvVar("HOMNI_LOGLEVEL");

    if (!logLevel.empty())
    {
        try
        {
            int logLevelIdx = stoi(logLevel);

            // set gOmniClientLogLevel
            if (logLevelIdx < OmniClientLogLevel::eOmniClientLogLevel_Debug)
            {
                OMNI_LOG_WARN(kHoudiniConnectorChannel, "Underflow log level: %s. Setting log level to Debug.", logLevelIdx);
                gOmniClientLogLevel = OmniClientLogLevel::eOmniClientLogLevel_Debug;
            }
            else if (logLevelIdx > OmniClientLogLevel::eOmniClientLogLevel_Error)
            {
                OMNI_LOG_WARN(kHoudiniConnectorChannel, "Overflow log level: %s. Setting log level to Error.", logLevelIdx);
                gOmniClientLogLevel = OmniClientLogLevel::eOmniClientLogLevel_Error;
            }
            else
            {
                gOmniClientLogLevel = static_cast<OmniClientLogLevel>(logLevelIdx);
            }
        }
        catch (...)
        {
            OMNI_LOG_ERROR(kHoudiniConnectorChannel, "Unknown log level from environment HOMNI_LOGLEVEL: %s", logLevel);
        }

        // set gHomniLogLevel
        if (gOmniClientLogLevel == OmniClientLogLevel::eOmniClientLogLevel_Debug)
        {
            gHomniLogLevel = homni::LogLevel_Debug;
        }
        else if (gOmniClientLogLevel == OmniClientLogLevel::eOmniClientLogLevel_Verbose)
        {
            gHomniLogLevel = homni::LogLevel_Verbose;
        }
        else if (gOmniClientLogLevel == OmniClientLogLevel::eOmniClientLogLevel_Info)
        {
            gHomniLogLevel = homni::LogLevel_Info;
        }
        else if (gOmniClientLogLevel == OmniClientLogLevel::eOmniClientLogLevel_Warning)
        {
            gHomniLogLevel = homni::LogLevel_Warning;
        }
        else if (gOmniClientLogLevel == OmniClientLogLevel::eOmniClientLogLevel_Error)
        {
            gHomniLogLevel = homni::LogLevel_Error;
        }
        else
        {
            OMNI_LOG_ERROR(kHoudiniConnectorChannel, "Failed setting log level. Unknown log level: %s", gOmniClientLogLevel);
        }
    }
}

static bool makeDirs(const string& path)
{
    string dir = path;

    // Normalize the path to use forward slashes.
    for (string::iterator iter = dir.begin(); iter != dir.end(); ++iter)
    {
        if (*iter == '\\')
        {
            *iter = '/';
        }
    }

    if (dir.back() != '/')
    {
        // The path does not end with a slash,
        // so trim the file name off.
        // Find the last slash in the path.
        string::size_type slashPos = dir.rfind('/');

        if (slashPos != string::npos)
        {
            dir = dir.substr(0, slashPos + 1);
        }
    }


    return fs::create_directories(dir.c_str());
}


static bool saveContentToFile(const char* path, const homni::Content& content, homni::ClientStatusResult* errLog)
{
    std::ofstream cacheFile(path, ios::out | ios::binary);

    cacheFile.write(reinterpret_cast<const char*>(content.buffer), content.size);

    cacheFile.close();

    if (!cacheFile)
    {
        if (errLog)
        {
            std::string msg("Error writing file ");
            msg += path;
            errLog->set(0, msg.c_str());
        }

        return false;
    }

    return true;
}

static bool loadFileContent(const char* path, std::vector<char>& outContent, homni::ClientStatusResult* errLog)
{
    ifstream ifs(path, ios::binary | ios::ate);
    if (!ifs.good())
    {
        if (errLog)
        {
            string msg("Error opening file '");
            msg += path;
            msg += "'";
            errLog->set(0, msg.c_str());
        }

        return false;
    }

    ifstream::pos_type pos = ifs.tellg();

    if (pos <= 0)
    {
        if (errLog)
        {
            errLog->set(0, "Invalid buffer size for file read.");
        }
        return false;
    }

    outContent.resize(pos);

    ifs.seekg(0, ios::beg);
    if (!ifs.read(outContent.data(), pos))
    {
        if (errLog)
        {
            string msg("Error reading file '");
            msg += path;
            msg += "' from disk";
            errLog->set(0, msg.c_str());
        }
        return false;
    }

    return true;
}

static bool parseOmniPath(const char* omniPath, string& outRelativePath, string& outServer, string& outUser, string& outPort)
{
    if (!OmniUtils::isOmniversePath(omniPath))
    {
        return false;
    }

    string stripped = OmniUtils::stripOmniSignature(omniPath);

    // Check if this could be a url of the form 'omni://<server>' or 'omniverse://<server>'.
    if (stripped.size() < 3 || stripped[0] != '/' || stripped[1] != '/' || stripped[2] == '/')
    {
        // The stripped path is too short, doesn't start wih "//" or starts with "///", so
        // it doesn't fit the pattern.
        outRelativePath = stripped;
        return true;
    }

    // Try to find the slash separator after the server specification.

    // Advance past the first two slashes.
    stripped = stripped.substr(2);

    // Find the next slash.
    size_t slashIdx = stripped.find("/");

    if (slashIdx != string::npos)
    {
        outRelativePath = stripped.substr(slashIdx);
        stripped = stripped.substr(0, slashIdx);
    }
    else
    {
        // There is no other slash, so the path following
        // the url prefix is empty.
        outRelativePath = "";
    }

    // Check for user name.

    // Find the next ampersand separator.
    size_t amperIdx = stripped.find("@");

    if (amperIdx != string::npos)
    {
        outUser = stripped.substr(0, amperIdx);
        if (amperIdx < stripped.size() - 1)
        {
            stripped = stripped.substr(amperIdx + 1);
        }
    }

    // Check for the port.

    // Find the next colon separator.
    size_t colonIdx = stripped.find(":");

    if (colonIdx != string::npos)
    {
        // Found a colon.
        outServer = stripped.substr(0, colonIdx);
        if (colonIdx < stripped.size() - 1)
        {
            outPort = stripped.substr(colonIdx + 1);
        }
    }
    else
    {
        // No colon found, so no port number.
        outServer = stripped;
    }

    return true;
}

static string getShortPath(const string& longPath)
{
    char shortPath[_MAX_PATH] = { '\0' };
    GetShortPathName(longPath.c_str(), shortPath, _MAX_PATH);
    return shortPath;
}

static bool getCachePathStr(const char* serverPath, std::string& outPath, bool createDirs, homni::ClientStatusResult* log = nullptr)
{
    string cacheDir = homni::Client::getCacheDir();

    if (serverPath)
    {
        std::string relPath, serverName, user, port;

        if (!parseOmniPath(serverPath, relPath, serverName, user, port))
        {
            return false;
        }

        if (serverName.empty())
        {
            return false;
        }

        if (std::string(serverPath).length() > 0 && serverPath[0] != '/' && serverPath[0] != '\\')
        {
            cacheDir += "/";
        }

        cacheDir += relPath;
    }

    fs::path result(cacheDir);
    result = result.lexically_normal();

    if (fs::exists(result))
    {
        // File already exists, try to generate
        // a short path to it.
        string longPath = result.string();
        string shortPath = getShortPath(longPath);
        outPath = shortPath.empty() ? longPath : shortPath;
        return true;
    }

    fs::path resultDir(result);
    resultDir.remove_filename();

    if (createDirs && !fs::is_directory(resultDir))
    {
        std::error_code ec;
        fs::create_directories(resultDir, ec);
        if (ec)
        {
            if (log)
            {
                string msg("Couldn't create directory for cache path ");
                msg += result.string();
                log->set(0, msg.c_str());
            }
            return false;
        }
    }

    if (fs::is_directory(resultDir))
    {
        // Try to generate a short path for the directory.
        string shortPath = getShortPath(resultDir.string());

        if (!shortPath.empty())
        {
            fs::path fileName = result.filename();
            result = shortPath;
            result /= fileName;
        }
    }

    outPath = result.string();

    return true;
}

static void logCallback(const char* threadName, const char* component, OmniClientLogLevel level, const char* message) OMNICLIENT_NOEXCEPT
{
    std::unique_lock<std::mutex> logOutputLock(gLogOutputMutex);

    std::stringstream ss;
    ss << threadName << ": " << component << ": " << message << "\n";

    // set gHomniLogLevel
    if (level == OmniClientLogLevel::eOmniClientLogLevel_Debug)
    {
        OMNI_LOG_VERBOSE(kOmniClientChannel, ss.str().c_str());
    }
    else if (level == OmniClientLogLevel::eOmniClientLogLevel_Verbose)
    {
        OMNI_LOG_VERBOSE(kOmniClientChannel, ss.str().c_str());
    }
    else if (level == OmniClientLogLevel::eOmniClientLogLevel_Info)
    {
        OMNI_LOG_INFO(kOmniClientChannel, ss.str().c_str());
    }
    else if (level == OmniClientLogLevel::eOmniClientLogLevel_Warning)
    {
        OMNI_LOG_WARN(kOmniClientChannel, ss.str().c_str());
    }
    else if (level == OmniClientLogLevel::eOmniClientLogLevel_Error)
    {
        OMNI_LOG_ERROR(kOmniClientChannel, ss.str().c_str());
    }
    else
    {
        OMNI_LOG_ERROR(kOmniClientChannel, ss.str().c_str());
        ;
    }
}

static void connectionStatusCallback(void* userData, const char* url, OmniClientConnectionStatus status) OMNICLIENT_NOEXCEPT
{
    if (!url || std::string(url).length() == 0)
    {
        return;
    }

    std::unique_lock<std::mutex> connectionsUpdateLock(gConnectionsUpdateMutex);

    switch (status)
    {
        case eOmniClientConnectionStatus_Connecting: ///< Attempting to connect
            OMNI_LOG_INFO("Connection Status: %s Connecting", url);
            break;
        case eOmniClientConnectionStatus_Connected: ///< Successfully connected
            OMNI_LOG_INFO("Connection Status: %s Connected", url);
            gOpenConnections.insert(url);
            gOpenConnectionsUpdateCount += 1;
            break;
        case eOmniClientConnectionStatus_ConnectError: ///< Connection error while trying to connect
            OMNI_LOG_ERROR("Connection Status: %s Connect Error", url);
            gOpenConnections.erase(url);
            gOpenConnectionsUpdateCount += 1;
            break;
        case eOmniClientConnectionStatus_Disconnected: ///< Disconnected
            OMNI_LOG_INFO("Connection Status: %s Disconnected", url);
            gOpenConnections.erase(url);
            gOpenConnectionsUpdateCount += 1;
            break;
        case eOmniClientConnectionStatus_SignedOut: ///< omniClientSignOut called
            OMNI_LOG_INFO("Connection Status: %s Singned out", url);
            gOpenConnections.erase(url);
            gOpenConnectionsUpdateCount += 1;
            break;
        case eOmniClientConnectionStatus_NoUsername: ///< No username was provided (this can only happen when connecting to servers without discovery)
            OMNI_LOG_ERROR("Connection Status: %s No User Name", url);
            gOpenConnections.erase(url);
            gOpenConnectionsUpdateCount += 1;
            break;
        case eOmniClientConnectionStatus_AuthAbort: ///< Application returned an abort code in the callback provided to omniClientRegisterAuthCallback
            OMNI_LOG_INFO("Connection Status: %s Authorization Aborted", url);
            gOpenConnections.erase(url);
            gOpenConnectionsUpdateCount += 1;
            break;
        case eOmniClientConnectionStatus_AuthCancelled: ///< User clicked "Cancel" or the application called omniClientAuthenticationCancel
            OMNI_LOG_INFO("Connection Status: %s Authorization Cancelled", url);
            gOpenConnections.erase(url);
            gOpenConnectionsUpdateCount += 1;
            break;
        case eOmniClientConnectionStatus_AuthError: ///< Internal error while trying to authenticate
            OMNI_LOG_ERROR("Connection Status: %s Authorization Error", url);
            gOpenConnections.erase(url);
            gOpenConnectionsUpdateCount += 1;
            break;
        case eOmniClientConnectionStatus_AuthFailed: ///< Authentication failed
            OMNI_LOG_ERROR("Connection Status: %s Authorization Failed", url);
            gOpenConnections.erase(url);
            gOpenConnectionsUpdateCount += 1;
            break;
        case eOmniClientConnectionStatus_ServerIncompatible: ///< The server is not compatible with this version of the client library
            OMNI_LOG_ERROR("Connection Status: %s Server Imcompatible", url);
            gOpenConnections.erase(url);
            gOpenConnectionsUpdateCount += 1;
            break;

        default:
            OMNI_LOG_ERROR("Unknown connection status %d - %s", status, url);
            break;
    }
}

static uint32_t getPathTypeFlags(uint64_t omniClientFlags)
{
    uint32_t result = 0;

    if (omniClientFlags & fOmniClientItem_ReadableFile)
        result |= homni::PathTypeFlags::PathType_ReadableFile;

    if (omniClientFlags & fOmniClientItem_WriteableFile)
        result |= homni::PathTypeFlags::PathType_WriteableFile;

    if (omniClientFlags & fOmniClientItem_CanHaveChildren)
        result |= homni::PathTypeFlags::PathType_CanHaveChildren;

    if (omniClientFlags & fOmniClientItem_DoesNotHaveChildren)
        result |= homni::PathTypeFlags::PathType_DoesNotHaveChildren;

    if (omniClientFlags & fOmniClientItem_IsMount)
        result |= homni::PathTypeFlags::PathType_IsMount;

    if (omniClientFlags & fOmniClientItem_IsInsideMount)
        result |= homni::PathTypeFlags::PathType_IsInsideMount;

    if (omniClientFlags & fOmniClientItem_CanLiveUpdate)
        result |= homni::PathTypeFlags::PathType_CanLiveUpdate;

    if (omniClientFlags & fOmniClientItem_IsOmniObject)
        result |= homni::PathTypeFlags::PathType_IsOmniObject;

    if (omniClientFlags & fOmniClientItem_IsChannel)
        result |= homni::PathTypeFlags::PathType_IsChannel;

    return result;
}

static uint32_t getPathAccess(const uint32_t omniAccess)
{
    uint32_t result = 0;

    if (omniAccess & OmniClientAccessFlags::fOmniClientAccess_Read)
        result |= homni::PathAccessType::PathAccess_Read;

    if (omniAccess & OmniClientAccessFlags::fOmniClientAccess_Write)
        result |= homni::PathAccessType::PathAccess_Write;

    if (omniAccess & OmniClientAccessFlags::fOmniClientAccess_Admin)
        result |= homni::PathAccessType::PathAccess_Admin;

    return result;
}


namespace homni
{

bool Client::connected()
{
    std::unique_lock<std::mutex> connectionsUpdateLock(gConnectionsUpdateMutex);
    return !gOpenConnections.empty();
}

void Client::listConnections(ClientStringResultContainer& result)
{
    std::unique_lock<std::mutex> connectionsUpdateLock(gConnectionsUpdateMutex);
    for (std::string conn : gOpenConnections)
    {
        result.insert(conn.c_str());
    }
}

int Client::connectionUpdateCount()
{
    std::unique_lock<std::mutex> connectionsUpdateLock(gConnectionsUpdateMutex);
    return gOpenConnectionsUpdateCount;
}

void Client::shutDown()
{
    omniClientLiveWaitForPendingUpdates();

    omniClientShutdown();
}


bool Client::initialize()
{
    if (gOmniClientInitialized)
    {
        return true;
    }

    initDefaults();

    omniClientSetLogCallback(logCallback);
    omniClientSetLogLevel(gOmniClientLogLevel);

    // Initialize omni client
    if (!omniClientInitialize(kOmniClientVersion))
    {
        return false;
    }

    omniClientRegisterConnectionStatusCallback(nullptr, connectionStatusCallback);

    initCacheDir();

    gLog.init();

    gOmniClientInitialized = true;

    return true;
}


bool Client::listPaths(const char* path, ClientPathResultContainer& outList, ClientStatusResult* errLog)
{
    struct ListContext
    {
        OmniClientResult status = OmniClientResult::eOmniClientResult_Ok;
        ClientPathResultContainer* results = nullptr;
    } listContext;

    OmniClientListCallback listCallback = [](void* userPtr, OmniClientResult result, uint32_t numEntries, OmniClientListEntry const* entries)
                                              OMNICLIENT_NOEXCEPT {
                                                  ListContext& listContext = *(ListContext*)userPtr;
                                                  listContext.status = result;

                                                  if (listContext.status == OmniClientResult::eOmniClientResult_Ok)
                                                  {
                                                      for (uint32_t i = 0; i < numEntries; ++i)
                                                      {
                                                          PathInfo info = {};
                                                          info.access = getPathAccess(entries[i].access);
                                                          info.modifiedTimestampNs = entries[i].modifiedTimeNs;
                                                          info.createdTimestampNs = entries[i].createdTimeNs;
                                                          info.pathType = getPathTypeFlags(entries[i].flags);
                                                          info.size = entries[i].size;

                                                          listContext.results->insert(entries[i].relativePath, info, entries[i].version);
                                                      }
                                                  }
                                              };

    listContext.results = &outList;

    omniClientWait(omniClientList(path, &listContext, listCallback));

    if (listContext.status != OmniClientResult::eOmniClientResult_Ok && errLog)
    {
        errLog->set(listContext.status, omniClientGetResultString(listContext.status));
    }

    return listContext.status == OmniClientResult::eOmniClientResult_Ok;
}

bool Client::stat(const char* path, ClientPathResult& outResult, ClientStatusResult* errLog)
{
    struct StatContext
    {
        OmniClientResult status = OmniClientResult::eOmniClientResult_Ok;
        ClientPathResult* result = nullptr;
    } statContext;

    OmniClientStatCallback statCallback = [](void* userPtr, OmniClientResult result, OmniClientListEntry const* entry) OMNICLIENT_NOEXCEPT {
        StatContext& statContext = *(StatContext*)userPtr;
        statContext.status = result;
        if (statContext.status == OmniClientResult::eOmniClientResult_Ok)
        {
            PathInfo info = {};
            info.access = getPathAccess(entry->access);
            info.modifiedTimestampNs = entry->modifiedTimeNs;
            info.createdTimestampNs = entry->createdTimeNs;
            info.pathType = getPathTypeFlags(entry->flags);
            info.size = entry->size;

            statContext.result->set(entry->relativePath, info, entry->version);
        }
    };

    statContext.result = &outResult;

    omniClientWait(omniClientStat(path, &statContext, statCallback));

    if (statContext.status != OmniClientResult::eOmniClientResult_Ok && errLog)
    {
        errLog->set(statContext.status, omniClientGetResultString(statContext.status));
    }

    return statContext.status == OmniClientResult::eOmniClientResult_Ok;
}

bool Client::copyFile(const char* srcUrl, const char* dstUrl, bool overWrite, ClientStatusResult* errLog)
{
    struct CopyContext
    {
        OmniClientResult status = OmniClientResult::eOmniClientResult_Ok;
    } copyContext;

    OmniClientCopyCallback copyCallback = [](void* userData, OmniClientResult result) OMNICLIENT_NOEXCEPT {
        CopyContext& copyContext = *(CopyContext*)userData;
        copyContext.status = result;
    };

    OmniClientCopyBehavior behavior = overWrite ? eOmniClientCopy_Overwrite : eOmniClientCopy_ErrorIfExists;

    std::string checkpointMessage;
    {
        std::unique_lock<std::mutex> lock(gCheckpointMessageMutex);
        checkpointMessage = gCheckpointMessage;
    }

    omniClientWait(omniClientCopy(srcUrl, dstUrl, &copyContext, copyCallback, behavior, checkpointMessage.c_str()));

    if (copyContext.status != OmniClientResult::eOmniClientResult_Ok && errLog)
    {
        errLog->set(copyContext.status, omniClientGetResultString(copyContext.status));
    }

    return copyContext.status == OmniClientResult::eOmniClientResult_Ok;
}

bool Client::createFolder(const char* url, ClientStatusResult* errLog)
{
    struct CreateFolderContext
    {
        OmniClientResult status = OmniClientResult::eOmniClientResult_Ok;
    } createFolderContext;

    OmniClientCreateFolderCallback createFolderCallback = [](void* userData, OmniClientResult result) OMNICLIENT_NOEXCEPT {
        CreateFolderContext& createFolderContext = *(CreateFolderContext*)userData;
        createFolderContext.status = result;
    };

    omniClientWait(omniClientCreateFolder(url, &createFolderContext, createFolderCallback));

    if (createFolderContext.status != OmniClientResult::eOmniClientResult_Ok && errLog)
    {
        errLog->set(createFolderContext.status, omniClientGetResultString(createFolderContext.status));
    }

    return createFolderContext.status == OmniClientResult::eOmniClientResult_Ok;
}

bool Client::getLocalFile(const char* url, ClientStringResult& outLocalFilePath, ClientStatusResult* errLog)
{
    struct GetLocalFileContext
    {
        OmniClientResult status = OmniClientResult::eOmniClientResult_Ok;
        ClientStringResult* localFilePath;

    } getLocalFileContext;

    OmniClientGetLocalFileCallback getLocalFileCallback = [](void* userData, OmniClientResult result, char const* localFilePath) OMNICLIENT_NOEXCEPT {
        GetLocalFileContext& context = *(GetLocalFileContext*)userData;
        context.status = result;
        if (context.localFilePath)
        {
            context.localFilePath->set(localFilePath);
        }
    };

    getLocalFileContext.localFilePath = &outLocalFilePath;

    omniClientWait(omniClientGetLocalFile(url, true, &getLocalFileContext, getLocalFileCallback));

    if (getLocalFileContext.status != OmniClientResult::eOmniClientResult_Ok && errLog)
    {
        errLog->set(getLocalFileContext.status, omniClientGetResultString(getLocalFileContext.status));
    }

    return getLocalFileContext.status == OmniClientResult::eOmniClientResult_Ok;
}


bool Client::downloadContent(const char* path, Content& outContent, ClientStringResult* outVersion, ClientStatusResult* errLog)
{
    struct ReadContext
    {
        OmniClientResult status = OmniClientResult::eOmniClientResult_Ok;
        Content* result = nullptr;
        ClientStringResult* version;
    } readContext;

    OmniClientReadFileCallback readFileCallback = [](void* userData, OmniClientResult result, const char* version, OmniClientContent* content)
                                                      OMNICLIENT_NOEXCEPT {
                                                          ReadContext& readContext = *(ReadContext*)userData;
                                                          readContext.status = result;

                                                          if (content && readContext.status == OmniClientResult::eOmniClientResult_Ok)
                                                          {
                                                              readContext.result->buffer = content->buffer;
                                                              readContext.result->size = content->size;
                                                              readContext.result->free = content->free;

                                                              // Take ownership of the content by clearing the source buffer.
                                                              content->buffer = nullptr;
                                                              content->size = 0;

                                                              if (readContext.version)
                                                              {
                                                                  readContext.version->set(version);
                                                              }
                                                          }
                                                      };

    readContext.result = &outContent;
    readContext.version = outVersion;

    omniClientWait(omniClientReadFile(path, &readContext, readFileCallback));

    if (readContext.status != OmniClientResult::eOmniClientResult_Ok && errLog)
    {
        errLog->set(readContext.status, omniClientGetResultString(readContext.status));
    }

    return readContext.status == OmniClientResult::eOmniClientResult_Ok;
}


bool Client::downloadContentToCache(const char* omniPath,
                                    ClientStringResult* cacheFilePath,
                                    ClientStatusResult* log,
                                    Content* outContent,
                                    ClientStringResult* outVersion,
                                    bool force)
{
    struct StatResult : public ClientPathResult
    {
        void set(const char* inPath, const PathInfo& inInfo, const char* inVersion) override
        {
            info = inInfo;
            path = inPath ? inPath : "";
            version = inVersion ? inVersion : "";
        }
        std::string path;
        std::string version;
        PathInfo info;
    } statResult;

    if (!Client::stat(omniPath, statResult))
    {
        return false; // Couldn't stat file
    }

    // We use a cache to avoid downloading the same asset repeatedly, not only
    // for performance reasons, but also to help avoid potentially overwriting
    // a file in the cache directory while it's being read.

    std::unique_lock<std::mutex> itemLock;
    FetchedFileEntry* item = nullptr;

    item = gFetchMap.getItem(omniPath);
    itemLock = std::unique_lock<std::mutex>(item->mtx);

    if (!force && item->isValid(statResult.version.c_str(), statResult.info.modifiedTimestampNs))
    {
        // File is already cached.
        if (cacheFilePath)
        {
            cacheFilePath->set(item->cacheFilePath.c_str());
        }
        return true;
    }

    // File isn't cached, so try to download it now.
    bool success = true;

    string cachePathVal;
    success = ::getCachePathStr(omniPath, cachePathVal, true, log);

    if (success)
    {
        if (cacheFilePath)
        {
            cacheFilePath->set(cachePathVal.c_str());
        }

        success = copyFile(omniPath, cachePathVal.c_str(), true /*deleteDst*/, log);

        if (success)
        {
            // NB:  There is an idiosyncrasy in Houdini when loading hda's where Houdini will hang in an
            // infinte loop, repeatedly calling FS_OmniReadHelper::createStream(). The reason
            // for this observed behavior isn't clear, but I discovered that setting the file's modified time
            // to the server time stamp (as given by FS_OmniInfoHelper), prevents the issue, so we use this as
            // a workaround for now.  Doing this also helps us to validate the server modified time of the
            // cached file by checking its last write time in Client::getCachedFile().

            fs::path p(cachePathVal.c_str());

            // Sanity check.
            if (!fs::exists(p))
            {
                OMNI_LOG_ERROR(kHoudiniConnectorChannel, "Warning: can't access cached file %s", p.string());
                return false;
            }

            std::chrono::seconds sec(statResult.info.modifiedTimestampNs / 1000000000);
            fs::file_time_type::duration dur(sec);
            fs::file_time_type updateTime(dur);
            fs::last_write_time(p, updateTime);

            item->cacheFilePath = cachePathVal;
            item->version = statResult.version;
            item->modifiedTime = statResult.info.modifiedTimestampNs;
        }
    }

    return success;
}

void Client::freeContent(Content& content)
{
    if (content.free && content.buffer && content.size)
    {
        content.free(content.buffer);
        content.buffer = nullptr;
        content.size = 0;
    }
}

bool Client::uploadContent(const char* path, Content& content, ClientStatusResult* errLog)
{
    deleteFile(path);

    struct WriteContext
    {
        OmniClientResult status = OmniClientResult::eOmniClientResult_Ok;
    } writeContext;

    OmniClientWriteFileCallback writeFileCallback = [](void* userData, OmniClientResult result) OMNICLIENT_NOEXCEPT {
        WriteContext& writeContext = *(WriteContext*)userData;
        writeContext.status = result;
    };

    OmniClientContent omniContent;
    omniContent.buffer = content.buffer;
    omniContent.size = content.size;
    omniContent.free = nullptr;

    omniClientWait(omniClientWriteFile(path, &omniContent, &writeContext, writeFileCallback));

    if (writeContext.status != OmniClientResult::eOmniClientResult_Ok && errLog)
    {
        errLog->set(writeContext.status, omniClientGetResultString(writeContext.status));
    }

    return writeContext.status == OmniClientResult::eOmniClientResult_Ok;
}

bool Client::uploadContentFromCache(const char* omniPath, ClientStatusResult* log)
{
    bool success = true;

    string cachePathVal;
    success = ::getCachePathStr(omniPath, cachePathVal, false, log);

    if (success)
    {
        std::vector<char> contentBuf;

        success = loadFileContent(cachePathVal.c_str(), contentBuf, log);

        if (success)
        {
            Content content = { contentBuf.data(), contentBuf.size(), nullptr };
            success = uploadContent(omniPath, content, log);
        }
    }

    return success;
}


bool Client::deleteFile(const char* omniPath, ClientStatusResult* errLog)
{
    struct DeleteContext
    {
        OmniClientResult status = OmniClientResult::eOmniClientResult_Ok;
    } deleteContext;

    OmniClientDeleteCallback deleteCallback = [](void* userData, OmniClientResult result) OMNICLIENT_NOEXCEPT {
        DeleteContext& deleteContext = *(DeleteContext*)userData;
        deleteContext.status = result;
    };

    omniClientWait(omniClientDelete(omniPath, &deleteContext, deleteCallback));

    if (deleteContext.status != OmniClientResult::eOmniClientResult_Ok && errLog)
    {
        errLog->set(deleteContext.status, omniClientGetResultString(deleteContext.status));
    }

    return deleteContext.status == OmniClientResult::eOmniClientResult_Ok;
}

void Client::usdLiveProcess()
{
    omniClientLiveProcess();
}

bool Client::parseOmniPath(const char* omniPath,
                           ClientStringResult& outPath,
                           ClientStringResult& outHost,
                           ClientStringResult& outUser,
                           ClientStringResult& outPort)
{
    OmniClientUrl* url = omniClientBreakUrl(omniPath);

    bool success = (url != nullptr);

    if (url)
    {
        outPath.set(url->path);
        outHost.set(url->host);
        outUser.set(url->user);
        outPort.set(url->port);

        omniClientFreeUrl(url);
    }

    return success;
}

const char* Client::getCacheDir()
{
    return gCacheDir.c_str();
}

const char* Client::getLogFileBaseName()
{
    return HomniLog::logFileBaseName();
}


bool Client::getCachePath(const char* serverPath, ClientStringResult& outPath, bool createDirs, ClientStatusResult* log)
{
    string cachePath;

    bool success = ::getCachePathStr(serverPath, cachePath, createDirs, log);

    outPath.set(cachePath.c_str());

    return success;
}

void Client::setLogLevel(LogLevel level)
{
    OmniClientLogLevel omniClientLogLevel;
    omni::log::Level omniLogLevel;

    if (level == LogLevel_Debug)
    {
        omniClientLogLevel = OmniClientLogLevel::eOmniClientLogLevel_Debug;
        omniLogLevel = omni::log::Level::eVerbose;
    }
    else if (level == LogLevel_Verbose)
    {
        omniClientLogLevel = OmniClientLogLevel::eOmniClientLogLevel_Verbose;
        omniLogLevel = omni::log::Level::eVerbose;
    }
    else if (level == LogLevel_Info)
    {
        omniClientLogLevel = OmniClientLogLevel::eOmniClientLogLevel_Info;
        omniLogLevel = omni::log::Level::eInfo;
    }
    else if (level == LogLevel_Warning)
    {
        omniClientLogLevel = OmniClientLogLevel::eOmniClientLogLevel_Warning;
        omniLogLevel = omni::log::Level::eWarn;
    }
    else if (level == LogLevel_Error)
    {
        omniClientLogLevel = OmniClientLogLevel::eOmniClientLogLevel_Error;
        omniLogLevel = omni::log::Level::eError;
    }
    else
    {
        OMNI_LOG_ERROR(kHoudiniConnectorChannel, "Failed setting log level. Unknown log level: %s", level);
        return;
    }
    gHomniLogLevel = level;
    gOmniClientLogLevel = omniClientLogLevel;
    gOmniLogLevel = omniLogLevel;

    omniClientSetLogLevel(gOmniClientLogLevel);
    auto log = omniGetLogWithoutAcquire();
    log->setChannelLevel(kHoudiniConnectorChannel, omniLogLevel, omni::log::SettingBehavior::eOverride);
}

LogLevel Client::getLogLevel()
{
    return gHomniLogLevel;
}

void Client::normalizeUrl(const char* inUrl, ClientStringResult& outUrl)
{
    if (inUrl)
    {
        size_t bufSize = 512;
        char buf[512] = { '\0' };
        const char* result = omniClientNormalizeUrl(inUrl, buf, &bufSize);

        if (result)
        {
            outUrl.set(result);
        }
    }
}

void Client::pushBaseUrl(const char* baseUrl)
{
    omniClientPushBaseUrl(baseUrl);
}

bool Client::popBaseUrl(const char* baseUrl)
{
    return omniClientPopBaseUrl(baseUrl);
}

void Client::signOut(const char* url)
{
    omniClientSignOut(url);
}

void Client::reconnect(const char* url)
{
    omniClientReconnect(url);
}

const char* Client::getVersionString()
{
    return HOUDINIOMNI_BUILD_STRING;
}

void Client::makeRelativeUrl(const char* baseUrl, const char* otherUrl, ClientStringResult& outResult)
{
    size_t expectedSize = 0;
    omniClientMakeRelativeUrl(baseUrl, otherUrl, nullptr, &expectedSize);
    char* buf = new char[expectedSize];
    omniClientMakeRelativeUrl(baseUrl, otherUrl, buf, &expectedSize);
    outResult.set(buf);
    delete[] buf;
}

void Client::setCheckpointMessage(const char* msg)
{
    if (!msg)
    {
        return;
    }
    std::unique_lock<std::mutex> msg_lock(gCheckpointMessageMutex);
    gCheckpointMessage = msg;
}

void Client::clearCheckpointMessage()
{
    std::unique_lock<std::mutex> msg_lock(gCheckpointMessageMutex);
    gCheckpointMessage.clear();
}

const char* Client::getConnectorName()
{
    return kConnectorName;
}

} // End namespace homni
