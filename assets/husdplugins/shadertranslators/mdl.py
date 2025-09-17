# SPDX-FileCopyrightText: Copyright (c) 2020-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

################################################################################
# This is a module that encodes shader VOP nodes as standard USD shaders.
# The usdShaderTranslator() function at the bottom provides an entry point.
import os
import re
import types

import hou
import husd.shaderutils as utils
from husd.previewshadertranslator import PreviewShaderTranslator as PreviewTranslatorBase
from husd.previewshadertranslator import PreviewShaderTranslatorHelper as PreviewHelperBase
from husd.shadertranslator import ShaderTranslator as TranslatorBase
from husd.shadertranslator import ShaderTranslatorHelper as HelperBase
from pxr import Gf, Sdf, UsdShade

################################################################################
# Constants
Tag_MdlIsParm = "mdl_isparm"
Tag_MdlColorSpace = "mdl_colorspace"


################################################################################
# The class that implements the logic of encoding MDL shader VOP nodes
# to USD MDL shader primitives.
class MdlShaderTranslatorHelper(HelperBase):
    def __init__(self, translator_id, usd_stage, usd_material_path, usd_time_code):
        """Saves the common pieces of data as member variables."""
        HelperBase.__init__(self, translator_id, usd_stage, usd_material_path, usd_time_code)

    def createMaterialShader(self, shader_node, requested_shader_type, shader_node_output_name):
        """creates a usd shader primitive, sets its attributes,
        and links it to the usd material primitive passed in constructor.
        """
        usd_parent_graph = UsdShade.NodeGraph.Get(self.myUsdStage, self.myUsdMaterialPath)

        try:
            # Houdini 19.0
            shader_prim_path = self.usdShaderPrimitivePath(shader_node, usd_parent_graph)
        except TypeError:
            # Houdini 19.5
            shader_prim_path = self.usdShaderPrimitivePath(shader_node, usd_parent_graph, shader_node.name())

        shader_prim = self.defineUsdShader(shader_node, shader_prim_path)

        # Add the sourceAsset declaration.  Looks like this:
        # uniform token info:implementationSource = "sourceAsset"
        # uniform asset info:mdl:sourceAsset = @nvidia/core_definitions.mdl@
        # uniform token info:mdl:sourceAsset:subIdentifier = "flex_material"

        # Get the mdl path and material name parms.
        mdlasset_parm_name = "mdlasset"
        mdlassetsubid_parm_name = "mdlassetsubid"
        mdl_asset_parm = shader_node.parm(mdlasset_parm_name)
        mdl_asset_subid_parm = shader_node.parm(mdlassetsubid_parm_name)

        if mdl_asset_parm != None and mdl_asset_subid_parm != None:
            mdl_asset = mdl_asset_parm.evalAsString()
            shader_prim.SetSourceAsset(mdl_asset, "mdl")
            subid = mdl_asset_subid_parm.evalAsString()
            if subid == "":
                # No sub identifier specified, so use the file base name.
                subid = os.path.splitext(os.path.basename(mdl_path))[0]

            if hasattr(shader_prim, "SetSourceAssetSubIdentifier"):
                # This version of USD shader schema supports the
                # source asset subidentifier API.
                shader_prim.SetSourceAssetSubIdentifier(subid, "mdl")
            else:
                # No schema support, set a custom attribute for the subidentifier.
                attr_name = "info:mdl:sourceAsset:subIdentifier"
                new_attr = shader_prim.GetPrim().CreateAttribute(attr_name, Sdf.ValueTypeNames.Token)
                new_attr.Set(subid)

        # Connect the material surface output.
        shader_output = shader_prim.CreateOutput("out", Sdf.ValueTypeNames.Token)
        mat_output = self.myUsdMaterial.CreateOutput("mdl:surface", Sdf.ValueTypeNames.Token)
        UsdShade.ConnectableAPI.ConnectToSource(mat_output, shader_output)

        mat_output = self.myUsdMaterial.CreateOutput("mdl:displacement", Sdf.ValueTypeNames.Token)
        UsdShade.ConnectableAPI.ConnectToSource(mat_output, shader_output)

        mat_output = self.myUsdMaterial.CreateOutput("mdl:volume", Sdf.ValueTypeNames.Token)
        UsdShade.ConnectableAPI.ConnectToSource(mat_output, shader_output)

        for parm_tuple in shader_node.parmTuples():

            # Only process parms with the mdl parm tag.
            if parm_tuple.parmTemplate().tags().get("mdl_isparm") == None:
                continue

            parm_name = parm_tuple.name()

            parm_translator = self.parameterTranslator(parm_tuple)

            if parm_translator is None:
                continue

            # Create an attribute on the material prim and set its value.
            parm_translator.createAndSetAttrib(shader_prim, self.usdTimeCode())

        # Process color spaces for textures.
        for parm_tuple in shader_node.parmTuples():

            color_space_tag = parm_tuple.parmTemplate().tags().get("mdl_colorspace")
            if color_space_tag:
                tex_input = shader_prim.GetInput(color_space_tag)
                if tex_input:
                    color_space = parm_tuple.evalAsStrings()[0]
                    if color_space:
                        tex_input.GetAttr().SetColorSpace(color_space)

        self.setPreviewShaderMetadata(shader_prim, shader_node)


################################################################################
# A class that implements the logic of encoding MDL shader
# as a USD standard preview shader primitive (ie, surfacepreview).
# Main reason for this subclas is:
# - prevent scaling of texture values by parm values.  E.g., we
#   don't want to scale the diffuse texture by the diffuse
#   color parm.
class MdlPreviewShaderTranslatorHelper(PreviewHelperBase):
    def __init__(self, usd_stage, usd_material_path, usd_time_code):
        PreviewHelperBase.__init__(self, usd_stage, usd_material_path, usd_time_code)

    def usdPreviewShaderInputInfo(self, usd_main_shader, preview_input_name, preview_input_type, info):

        if info:
            # MDL does not scale texel values by parm value the texture drives.
            info.myTexAutoScaleFlag = False

        return info


################################################################################
class MdlShaderTranslator(TranslatorBase):
    """Translates MDL Houdini shader nodes into USD shader primitives.
    See husdshadertranslators.default.DefaultShaderTranslator for details.
    """

    def __init__(self):
        TranslatorBase.__init__(self)

        # Set pattern for matching the MDL render mask.
        self.myPattern = re.compile(r"\bMDL\b")

    def matchesRenderMask(self, render_mask):
        return bool(self.myPattern.search(render_mask))

    # As of this writing, this function is called from husdCreateMaterialShader() in
    # https://github.com/sideeffects/HoudiniUsdBridge/blob/master/src/houdini/lib/H_USD/HUSD/HUSD_CreateMaterial.C#L125
    # which, in turn, is invoked from the inner loop of HUSD_CreateMaterial::createMaterial()
    # in the same file.
    def createMaterialShader(self, usd_stage, usd_material_path, usd_time_code, shader_node, shader_type, output_name):
        if output_name not in ["out", "surface"]:
            return

        helper = MdlShaderTranslatorHelper(self.translatorID(), usd_stage, usd_material_path, usd_time_code)
        helper.createMaterialShader(shader_node, shader_type, output_name)

    def shaderTranslatorHelper(self, translator_id, usd_stage, usd_material_path, usd_time_code):
        return MdlShaderTranslatorHelper(translator_id, usd_stage, usd_material_path, usd_time_code)


################################################################################
class MdlPreviewShaderTranslator(PreviewTranslatorBase):
    """Translates MDL USD shader into USD standard preview shader."""

    def __init__(self):
        PreviewTranslatorBase.__init__(self)

        # Set pattern for matching the MDL render mask.
        self.myPattern = re.compile(r"\bMDL\b")

    def matchesRenderMask(self, render_mask):
        return bool(self.myPattern.search(render_mask))

    def previewShaderTranslatorHelper(self, usd_stage, usd_material_path, usd_time_code):
        return MdlPreviewShaderTranslatorHelper(usd_stage, usd_material_path, usd_time_code)


################################################################################
# In order to be considered for shader translation, this python module
# implements the function that returns a translator object.
# See husdplugins.shadertranslators.default.usdShaderTranslator() for details.
mdl_shader_tranlator = MdlShaderTranslator()


def usdShaderTranslator():
    return mdl_shader_tranlator


# See default.usdPreviewShaderTranslator() plugin for details.
mdl_preview_translator = MdlPreviewShaderTranslator()


def usdPreviewShaderTranslator():
    return mdl_preview_translator
