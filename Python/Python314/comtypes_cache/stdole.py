from enum import IntFlag

import comtypes.gen._00020430_0000_0000_C000_000000000046_0_2_0 as __wrapper_module__
from comtypes.gen._00020430_0000_0000_C000_000000000046_0_2_0 import (
    OLE_COLOR, BSTR, Library, DISPPARAMS, FONTSIZE, IUnknown,
    IDispatch, _check_version, VgaColor, CoClass, OLE_YPOS_PIXELS,
    OLE_YSIZE_HIMETRIC, Monochrome, FONTSTRIKETHROUGH,
    OLE_XSIZE_CONTAINER, DISPPROPERTY, OLE_YSIZE_CONTAINER,
    IPictureDisp, OLE_XPOS_PIXELS, COMMETHOD, IFontDisp, FONTNAME,
    StdPicture, OLE_CANCELBOOL, FONTITALIC, OLE_OPTEXCLUSIVE,
    OLE_YSIZE_PIXELS, OLE_XPOS_HIMETRIC, IFont, Unchecked, Checked,
    FontEvents, OLE_XSIZE_HIMETRIC, FONTUNDERSCORE, dispid, Color,
    OLE_YPOS_CONTAINER, Font, OLE_HANDLE, OLE_YPOS_HIMETRIC, Picture,
    typelib_path, DISPMETHOD, Default, OLE_ENABLEDEFAULTBOOL, HRESULT,
    IPicture, _lcid, VARIANT_BOOL, IEnumVARIANT, IFontEventsDisp,
    OLE_XPOS_CONTAINER, StdFont, EXCEPINFO, Gray, GUID, FONTBOLD,
    OLE_XSIZE_PIXELS
)


class OLE_TRISTATE(IntFlag):
    Unchecked = 0
    Checked = 1
    Gray = 2


class LoadPictureConstants(IntFlag):
    Default = 0
    Monochrome = 1
    VgaColor = 2
    Color = 4


__all__ = [
    'OLE_COLOR', 'OLE_OPTEXCLUSIVE', 'OLE_YSIZE_PIXELS', 'Library',
    'OLE_XPOS_HIMETRIC', 'OLE_CANCELBOOL', 'IFont', 'FONTSIZE',
    'Checked', 'FontEvents', 'VgaColor', 'OLE_XSIZE_HIMETRIC',
    'FONTUNDERSCORE', 'OLE_YPOS_PIXELS', 'OLE_YSIZE_HIMETRIC',
    'Color', 'OLE_YPOS_CONTAINER', 'Font', 'OLE_HANDLE', 'Monochrome',
    'FONTSTRIKETHROUGH', 'OLE_XSIZE_CONTAINER', 'OLE_YPOS_HIMETRIC',
    'Picture', 'typelib_path', 'Default', 'OLE_YSIZE_CONTAINER',
    'OLE_ENABLEDEFAULTBOOL', 'IPictureDisp', 'IPicture',
    'OLE_XPOS_PIXELS', 'IFontEventsDisp', 'OLE_XPOS_CONTAINER',
    'LoadPictureConstants', 'IFontDisp', 'StdFont', 'FONTNAME',
    'Gray', 'OLE_TRISTATE', 'Unchecked', 'FONTBOLD', 'StdPicture',
    'FONTITALIC', 'OLE_XSIZE_PIXELS'
]

