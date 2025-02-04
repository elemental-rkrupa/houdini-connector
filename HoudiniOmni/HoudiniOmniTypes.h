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
#include "houdiniomni_export.h"

#include <cstddef>
#include <cstdint>

namespace homni
{

enum PathTypeFlags : uint32_t
{
    // You can call omniClientReadFile on this
    // note: ACLs may still prevent you from reading it
    PathType_ReadableFile = 1 << 0,

    // You can call omniClientWriteFile on this
    // note ACLs may still prevent you from writing it
    PathType_WriteableFile = 1 << 1,

    // This thing can contain other things (a folder-like thing)
    PathType_CanHaveChildren = 1 << 2,

    // This thing does not have any children.
    // The lack of this flag does not mean it does have children!
    // Sometimes we are not sure if it has children until you attempt to list the children.
    // This is only intended to be used for UI elements to hide the "expand" button if we
    // are sure it does not have any children.
    PathType_DoesNotHaveChildren = 1 << 3,

    // This thing is the root of a mount point
    PathType_IsMount = 1 << 4,

    // This thing is located inside a mounted folder
    PathType_IsInsideMount = 1 << 5,

    // This thing supports live updates
    PathType_CanLiveUpdate = 1 << 6,

    // This thing is in omni-object format
    // You must use a special API to read/write it
    PathType_IsOmniObject = 1 << 7,

    // You can call omniClientJoinChannel on this
    PathType_IsChannel = 1 << 8,

    // This item is checkpointed (meaning you can revert to it)
    PathType_IsCheckpointed = 1 << 9
};

enum PathAccessType : uint32_t
{
    // Undefined
    PathAccess_None = 0,

    // Can read this thing
    PathAccess_Read = 1 << 0,

    // Can write to this thing
    PathAccess_Write = 1 << 1,

    // Can change ACLs for this thing
    PathAccess_Admin = 1 << 2,

    PathAccess_Full = PathAccess_Admin | PathAccess_Write | PathAccess_Read
};

enum LogLevel
{
    LogLevel_Debug, // Extra chatty
    LogLevel_Verbose, // Chatty
    LogLevel_Info, // Not a problem
    LogLevel_Warning, // Potential problem
    LogLevel_Error, // Definite problem
};

struct HOUDINIOMNI_EXPORT PathInfo
{
    uint32_t access;
    uint64_t modifiedTimestampNs;
    uint64_t createdTimestampNs;
    uint64_t pathType;
    uint64_t size;
    uint64_t cacheTimestamp; // Time when PathInfo was cached.
};

struct HOUDINIOMNI_EXPORT Content
{
    void* buffer;
    size_t size;
    void (*free)(void* buffer); // Function to call to free the buffer
};


// The following abstract classes allow safely returning string and POD items accross the DLL boundary.

class ClientPathResultContainer
{
public:
    virtual void insert(const char* path, const PathInfo& info, const char* version) = 0;
};

class ClientPathResult
{
public:
    virtual void set(const char* path, const PathInfo& info, const char* version) = 0;
};

class ClientStatusResult
{
public:
    virtual void set(uint64_t status, const char* statusDescription) = 0;
};

class ClientStringResult
{
public:
    virtual void set(const char* value) = 0;
};

class ClientStringResultContainer
{
public:
    virtual void insert(const char* value) = 0;
};

} // namespace homni
