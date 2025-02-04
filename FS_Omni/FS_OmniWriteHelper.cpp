// SPDX-FileCopyrightText: Copyright (c) 2019-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: LicenseRef-NvidiaProprietary
//
// NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
// property and proprietary rights in and to this material, related
// documentation and any modifications thereto. Any use, reproduction,
// disclosure or distribution of this material and related documentation
// without an express license agreement from NVIDIA CORPORATION or
// its affiliates is strictly prohibited.

#include "FS_OmniWriteHelper.h"

#include "FS_Omni.h"
#include "HoudiniOmni.h"
#include "HoudiniOmniResultTypes.h"
#include "HoudiniOmniUtils.h"

#include <UT/UT_DirUtil.h>
#include <fstream>

using namespace std;

namespace
{

// Sends writer stream data to Omniverse when the stream is destroyed.
// The current implementation sends the entire contents of the file
// to the server all at once as a single blob, which is inefficient.
// We should attempt to refactor this to use a custom ostream buffer
// to send the data incrementally, in smaller chunks.
//
class FS_OmniWriterStream : public FS_WriterStream
{
public:
    FS_OmniWriterStream(const string& omniPath, const char* cachePath) : FS_WriterStream(cachePath), m_omniPath(omniPath)
    {
    }

    ~FS_OmniWriterStream()
    {
        this->destroy(false);
    }

protected:
    std::string m_omniPath;

    virtual bool destroy(bool removefile) override
    {
        FS_WriterStream::destroy(false);

        homni::StatusResult status;
        if (!homni::Client::copyFile(myFile, m_omniPath.c_str(), true /*deleteDst*/, &status))
        {
            cerr << "Error saving to " << m_omniPath << ".  Error code: " << status.status << ", description: '" << status.description << "'" << endl;
        }

        return true;
    }
};

} // End anonymous namespace

namespace homni
{

FS_OmniWriteHelper::FS_OmniWriteHelper()
{
}

FS_OmniWriteHelper::~FS_OmniWriteHelper()
{
}

FS_WriterStream* FS_OmniWriteHelper::createStream(const char* source)
{
    FS_WriterStream* os = nullptr;

    if (OmniUtils::isOmniversePath(source))
    {
        StringResult cachePath;

        if (Client::getCachePath(source, cachePath) && !cachePath.val.empty())
        {
            os = new FS_OmniWriterStream(source, cachePath.val.c_str());
        }
        else
        {
            cerr << "Error getting cache path for server path " << source << endl;
        }
    }

    return os;
}

bool FS_OmniWriteHelper::canMakeDirectory(const char* source)
{
    // Return true is this is an Omniverse URL and the file doesn't already exist.
    PathInfoResult statResult;
    return OmniUtils::isOmniversePath(source) && !Client::stat(source, statResult);
}

bool FS_OmniWriteHelper::makeDirectory(const char* source, mode_t mode, bool ignore_umask)
{
    StatusResult err;
    if (!Client::createFolder(source, &err))
    {
        cerr << "Creating folder " << source << " failed.\n";
        if (!err.description.empty())
        {
            cerr << err.description << endl;
        }
        return false;
    }

    return true;
}

} // namespace homni
