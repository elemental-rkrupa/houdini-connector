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

#include <FS/FS_Reader.h>

namespace homni
{

class FS_OmniReadHelper : public FS_ReaderHelper
{
public:
    FS_OmniReadHelper();
    virtual ~FS_OmniReadHelper();

    virtual FS_ReaderStream* createStream(const char* source, const UT_Options* options);

    // Overriding to allow handling the '?' character for checkpoints.
    virtual bool splitIndexFileSectionPath(const char* source_section_path, UT_String& index_file_path, UT_String& section_name);
};


} // namespace homni
