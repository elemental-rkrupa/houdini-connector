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

#include <cstring>
#include <string>

namespace homni
{

// Header-only Omniverse utilities.
class OmniUtils
{
public:
    static const char* omniSignature()
    {
        return "omni:";
    }

    static const char* omniverseSignature()
    {
        return "omniverse:";
    }

    static const char* omniverseFileSystemPrefix()
    {
        return "omniverse:/";
    }

    // The following constant must match the length of the string
    // returned by omniSignature() above.
    static const int kOmniSignatureLen = 5;

    // The following constant must match the length of the string
    // returned by omniverseSignature() above.
    static const int kOmniverseSignatureLen = 10;

    // Returns true if the given path has the omni signature prefix.
    // Returns false otherwise.
    static bool hasOmniSignature(const char* path)
    {
        return path && strncmp(omniSignature(), path, kOmniSignatureLen) == 0;
    }

    // Returns true if the given path has the omniverse signature prefix.
    // Returns false otherwise.
    static bool hasOmniverseSignature(const char* path)
    {
        return path && strncmp(omniverseSignature(), path, kOmniverseSignatureLen) == 0;
    }

    static bool isOmniversePath(const char* path)
    {
        return hasOmniSignature(path) || hasOmniverseSignature(path);
    }

    // If the given path has an omniverse prefix, returns
    // the portion of the path following the prefix.
    // Otherwise, returns the original path unchanged.
    static const char* stripOmniSignature(const char* path)
    {
        if (OmniUtils::hasOmniSignature(path))
        {
            return &path[OmniUtils::kOmniSignatureLen];
        }

        if (OmniUtils::hasOmniverseSignature(path))
        {
            return &path[OmniUtils::kOmniverseSignatureLen];
        }

        return path;
    }

    static bool getRelativeServerPath(const char* path, std::string& outRelativePath)
    {
        if (!path || !isOmniversePath(path))
        {
            return false;
        }

        const char* stripped = stripOmniSignature(path);

        size_t len = std::string(stripped).length();

        // Check if this could be a url of the form 'omni://<server>' or 'omniverse://<server>'.
        if (len < 3 || stripped[0] != '/' || stripped[1] != '/' || stripped[2] == '/')
        {
            // The stripped path is too short, doesn't start wih "//" or starts with "///", so
            // it doesn't fit the pattern.
            outRelativePath = stripped;
        }
        else
        {
            // Try to find the slash separator after the server specification.
            // Advance past the first two slashes.
            stripped += 2;

            // Find the next slash.
            const char* nextSlash = strchr(stripped, '/');

            // Return the substring starting at the next slash, or
            // an empty string if there is no other slash,
            // i.e., the path following the url prefix is empty.
            outRelativePath = nextSlash ? nextSlash : "";
        }

        return true;
    }

    static std::string getEnvVar(const char* name)
    {
#if defined(_WIN32)
        char value[1024];
        size_t len = 0;
        getenv_s(&len, value, sizeof(value), name);

        if (len > 0 && len <= sizeof(value))
        {
            return std::string(value);
        }
#else
        if (const char* env = getenv(name))
        {
            return std::string(env);
        }
#endif
        return {};
    }
};

} // namespace homni
