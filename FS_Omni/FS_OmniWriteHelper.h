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

#include <FS/FS_Writer.h>

namespace homni
{

class FS_OmniWriteHelper : public FS_WriterHelper
{
public:
    FS_OmniWriteHelper();
    virtual ~FS_OmniWriteHelper();

    virtual FS_WriterStream* createStream(const char* source) override;

    virtual bool canMakeDirectory(const char* source) override;

    virtual bool makeDirectory(const char* source, mode_t mode = 0777, bool ignore_umask = false) override;
};

} // namespace homni
