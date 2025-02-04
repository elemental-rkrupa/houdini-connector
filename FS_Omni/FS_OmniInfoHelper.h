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

#include <FS/FS_Info.h>
#include <SYS/SYS_Version.h>

#if SYS_VERSION_MAJOR_INT > 19 || (SYS_VERSION_MAJOR_INT == 19 && SYS_VERSION_MINOR_INT == 5)
typedef time_t ModTimeType;
#else
typedef int ModTimeType;
#endif

class OmniPathList;

namespace homni
{

class FS_OmniInfoHelper : public FS_InfoHelper
{
public:
    FS_OmniInfoHelper();
    virtual ~FS_OmniInfoHelper();

    virtual bool isPathValid(const char* source);
    virtual bool canHandle(const char* source);
    virtual bool hasAccess(const char* source, int mode);
    virtual bool getIsDirectory(const char* source);
    virtual ModTimeType getModTime(const char* source);
    virtual int64 getSize(const char* source);
    virtual UT_String getExtension(const char* source);
    virtual bool getContents(const char* source, UT_StringArray& contents, UT_StringArray* dirs);
};

} // namespace homni
