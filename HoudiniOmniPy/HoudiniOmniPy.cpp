// SPDX-FileCopyrightText: Copyright (c) 2020-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
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
#include "pybind11/functional.h"
#include "pybind11/pybind11.h"

#include <UT/UT_DirUtil.h>
#include <pybind11/stl.h>

namespace py = pybind11;

#include <iostream>
#include <string>
#include <vector>

using namespace homni;
using namespace std;

namespace homni
{
struct OmniUrl
{
    std::string path;
    std::string host;
    std::string user;
    std::string port;
};
} // namespace homni

namespace
{

std::vector<std::string> listContents(const char* omniUrl)
{
    PathStringResultVector pathResults;

    Client::listPaths(omniUrl, pathResults);

    return pathResults.items;
}

py::object omniStat(const char* omniUrl)
{
    PathInfoResult statResult;

    if (!Client::stat(omniUrl, statResult))
    {
        return py::none();
    }

    return py::cast(statResult.entry.info);
}

void deleteFile(const char* omniUrl)
{
    Client::deleteFile(omniUrl);
}

bool copyFile(const char* srcUrl, const char* dstUrl, bool deleteDst)
{
    StatusResult err;
    if (!Client::copyFile(srcUrl, dstUrl, deleteDst, &err))
    {
        cerr << "Copy failed.\n";
        if (!err.description.empty())
        {
            cerr << err.description << endl;
        }
        return false;
    }

    return true;
}

std::string getLocalFile(const char* url)
{
    StatusResult err;
    StringResult localFilePath;
    if (!Client::getLocalFile(url, localFilePath, &err))
    {
        cerr << "Getting local file failed.\n";
        if (!err.description.empty())
        {
            cerr << err.description << endl;
        }
        return "";
    }

    return localFilePath.val;
}

std::vector<std::string> listConnections()
{
    StringResultVector resultVec;

    Client::listConnections(resultVec);

    return resultVec.items;
}

std::string getServerPath(const char* path)
{
    std::string serverPath;
    OmniUtils::getRelativeServerPath(path, serverPath);

    return serverPath;
}

OmniUrl parseOmniPath(const char* path)
{
    StringResult serverPath;
    StringResult host;
    StringResult user;
    StringResult port;

    OmniUrl result;

    if (!Client::parseOmniPath(path, serverPath, host, user, port))
    {
        return OmniUrl();
    }

    result.path = serverPath.val;
    result.host = host.val;
    result.user = user.val;
    result.port = port.val;

    return result;
}

void addBookmark(const char* server)
{
    std::string pathPrefix("omniverse://");

    pathPrefix += std::string(server);

    UTaddAbsolutePathPrefix(pathPrefix.c_str());
}

std::string normalizeOmniPath(const char* url)
{
    StringResult result;
    Client::normalizeUrl(url, result);

    if (homni::OmniUtils::isOmniversePath(result.val.c_str()))
    {
        return result.val;
    }

    return url;
}

std::string download(const char* omniPath)
{
    StatusResult err;
    StringResult cacheFilePath;

    if (Client::downloadContentToCache(omniPath, &cacheFilePath, &err))
    {
        if (cacheFilePath.val.empty())
        {
            cerr << "Internal error: cache file path returned empty." << endl;
        }

        return cacheFilePath.val;
    }

    cerr << "Download failed.\n";
    if (!err.description.empty())
    {
        cerr << err.description << endl;
    }

    // Failure
    return std::string();
}

} // End anonymous namespace

PYBIND11_MODULE(client, m)
{
    m.doc() = "Omniverse client functions for Houdini.";

    m.def("initialize", &Client::initialize, "Initialize the Omniverse client.");

    m.def("shutdown",
          &Client::shutDown,
          "Shut down the Omni client library.  "
          "It's not safe to call any functions (not even initialize()) after calling this.");

    m.def("connected", &Client::connected, "Returns true if there are any open connections to the Omniverse server.");

    m.def("signOut", &Client::signOut, "Immediately disconnect from the server specified by this URL.");

    m.def("reconnect", &Client::reconnect, "Attempt to reconnect, even if the previous connection attempt failed.");

    m.def("listConnections", &listConnections, "Returns a list of the urls of the currentl opened connections.");

    m.def("connectionUpdateCount",
          &Client::connectionUpdateCount,
          "Number of times the list of open connections has been updated.  "
          "This value can be used to efficiently monitor the dirty state "
          "of the open connections list.");

    m.def("list", &listContents, "Returns a list of the contents of the given Omniverse URI.", py::arg("omniUri"));

    py::enum_<homni::PathAccessType>(m, "PathAccessType")
        .value("PathAccess_None", PathAccess_None)
        .value("PathAccess_Read", PathAccess_Read)
        .value("PathAccess_Write", PathAccess_Write)
        .value("PathAccess_Admin", PathAccess_Admin)
        .export_values();

    py::class_<homni::PathInfo>(m, "PathInfo")
        .def_readwrite("access", &PathInfo::access)
        .def_readwrite("modifiedTimeStampNs", &PathInfo::modifiedTimestampNs)
        .def_readwrite("createdTimeStampNs", &PathInfo::createdTimestampNs)
        .def_readwrite("pathType", &PathInfo::pathType)
        .def_readwrite("size", &PathInfo::size);

    m.def("stat",
          &omniStat,
          "Returns file information for the given Omniverse URI.  "
          "Returns an object of type homni.client.PathInfo on success.  "
          "Returns None on failure (e.g., if the path doesn't exist).",
          py::arg("omniUri"));

    m.def("copy",
          &copyFile,
          "Copies the file from the source path to the destination path.  "
          "If overWrite is true, the destination file will be overwritten "
          "if it exists.  If overWrite is false, the copy operation will "
          "fail if the destination exists.",
          py::arg("srcUrl"),
          py::arg("dstUrl"),
          py::arg("overWrite"));

    m.def("getLocalFile",
          &getLocalFile,
          "Get a local file name for the URL.  "
          "If the URL already points to a local file, it is returned directly.  "
          "Otherwise, this downloads the file to a local location and returns that location.  "
          "Returns the empty string on error.",
          py::arg("url"));

    m.def("delete", &deleteFile, "Deletes the given file from the server.", py::arg("omniUri"));

    m.def("usdLiveProcess", &Client::usdLiveProcess, "Process live updates received from the server.");

    m.def("getServerPath",
          &getServerPath,
          "If the given path is a well-formed Omniverse uri, this function returns the corresponding "
          "relative server path.  Returns an empty string otherwise.",
          py::arg("path"));

    m.def("isOmniversePath", &homni::OmniUtils::isOmniversePath, "Returns true if the given path has the 'omni:' or 'omniverse:' prefix.");

    py::class_<homni::OmniUrl>(m, "OmniUrl")
        .def_readwrite("path", &OmniUrl::path)
        .def_readwrite("host", &OmniUrl::host)
        .def_readwrite("user", &OmniUrl::user)
        .def_readwrite("port", &OmniUrl::port);

    m.def("parseOmniPath", &parseOmniPath, "Returns a struct containing the components of the given Omniverse URL.", py::arg("path"));

    m.def("pushBaseUrl", &Client::pushBaseUrl, "Pushes the given Omniverse URL on the stack of base URLs for resolving relative paths.");

    m.def("popBaseUrl",
          &Client::popBaseUrl,
          "Pop the given Omniverse URL from the stack of base URLs.  Returns false if the given URL is not at the top of the stack.");

    m.def("normalizeOmniPath", &normalizeOmniPath, "Returns a normalized version of the given URL.", py::arg("URL"));

    m.def("addBookmark",
          &addBookmark,
          "Create an absolute omniverse path prefix, containing the given server name, in Houdini's file browser.  "
          "E.g., for server name 'ov-rc', create the prefix 'omniverse://ov-rc'.",
          py::arg("serverName"));

    py::enum_<homni::LogLevel>(m, "LogLevel")
        .value("LogLevel_Debug", LogLevel_Debug)
        .value("LogLevel_Verbose", LogLevel_Verbose)
        .value("LogLevel_Info", LogLevel_Info)
        .value("LogLevel_Warning", LogLevel_Warning)
        .value("LogLevel_Error", LogLevel_Error)
        .export_values();

    m.def("setLogLevel", &Client::setLogLevel, "Set the client logging verbosity.", py::arg("logLevel"));

    m.def("getLogLevel", &Client::getLogLevel, "Get the currently set client logging verbosity.");

    m.def("download",
          &download,
          "Downloads the file at the given Omniverse uri from the server to the local disk cache directory.  "
          "Returns the path to the downloaded file.",
          py::arg("omniPath"));

    m.def("getVersionString", &Client::getVersionString, "Get the plugin version string.");

    m.def("getCacheDir", &Client::getCacheDir, "Get the local disk cache directory.");

    m.def("getLogFileBaseName", &Client::getLogFileBaseName, "Get the base name of the logging output file.");

    m.def("setCheckpointMessage", &Client::setCheckpointMessage, "Set the Omniverse checkpoint message for saving non-USD assets.");

    m.def("clearCheckpointMessage", &Client::clearCheckpointMessage, "Clear the Omniverse checkpoint message for saving non-USD assets.");

    m.def("getConnectorName", &Client::getConnectorName, "Return the Omniverse Connector name for Houdini Connector - HoudiniConnector");
}
