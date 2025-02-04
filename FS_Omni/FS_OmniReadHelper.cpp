// SPDX-FileCopyrightText: Copyright (c) 2019-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: LicenseRef-NvidiaProprietary
//
// NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
// property and proprietary rights in and to this material, related
// documentation and any modifications thereto. Any use, reproduction,
// disclosure or distribution of this material and related documentation
// without an express license agreement from NVIDIA CORPORATION or
// its affiliates is strictly prohibited.

#include "FS_OmniReadHelper.h"

#include "FS_Omni.h"
#include "HoudiniOmni.h"

#include <UT/UT_DirUtil.h>
#include <chrono>
#include <filesystem>

using namespace std;

namespace fs = std::filesystem;

namespace
{

// FS_OmniReaderStream can be used for reading downloaded
// server content from memory, without writing the data to
// a temporary file first.  Example usage:
//
// Content content = {};
// if (Client::downloadContent(source, content))
// {
//    is = new FS_OmniReaderStream(content, 0);
// }
//
class FS_OmniReaderStream : public FS_ReaderStream
{
public:
    FS_OmniReaderStream(homni::Content content, int modTime)
        : FS_ReaderStream(reinterpret_cast<const char*>(content.buffer), content.size, modTime), m_content(content)
    {
    }

    ~FS_OmniReaderStream()
    {
        homni::Client::freeContent(m_content);
    }

protected:
    homni::Content m_content;
};

// The string result struct must be defined locally in this
// file in an anonymous namespace, to avoid possible memory
// management crashes when passing strings accross shared
// library boundaries.
struct StringResult : public homni::ClientStringResult
{
    void set(const char* inVal) override
    {
        val = inVal ? inVal : "";
    }
    std::string val;
};

} // namespace


namespace homni
{

FS_OmniReadHelper::FS_OmniReadHelper()
{
}

FS_OmniReadHelper::~FS_OmniReadHelper()
{
}

// Overriding to allow handling the '?' character for checkpoints.
// See FS_Reader.h for documentation.
//
// Consideration: This function currently doesn't try to handle Houdini's native
// usage of '?' in paths, for designating section indices in files.  If
// we want to support Houdini's special '?' syntax in Omniverse URIs,
// we can look into further processing the path to also set the
// 'section_name' parameter.  The FS/FS_HomeHelper sample includes
// example code for doing this.
bool FS_OmniReadHelper::splitIndexFileSectionPath(const char* source_section_path, UT_String& index_file_path, UT_String& section_name)
{
    if (OmniUtils::isOmniversePath(source_section_path))
    {
        index_file_path = source_section_path;
        return true;
    }
    return false;
}

FS_ReaderStream* FS_OmniReadHelper::createStream(const char* source, const UT_Options* opts)
{
    // Basic sanity check.
    if (!source)
    {
        return nullptr;
    }

    size_t len = std::string(source).length();
    if (len == 0 || source[len - 1] == ':' || source[len - 1] == '/')
    {
        return nullptr;
    }

    FS_ReaderStream* is = nullptr;

    if (OmniUtils::isOmniversePath(source))
    {
        StringResult localPath;

        if (Client::getLocalFile(source, localPath) && !localPath.val.empty())
        {
            is = new FS_ReaderStream(localPath.val.c_str());
        }
    }

    return is;
}

} // namespace homni
