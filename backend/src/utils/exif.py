"""EXIF / GPS metadata extraction from an image file on disk.

Moved out of ``services/executors/builtin.py`` — metadata extraction is NOT a
pipeline node (it's a whole-pipeline setting, ``PipelineDefinition.extract_metadata``,
driven by ``PipelineExecutionService._maybe_extract_metadata``), so this has no
dependency on the executor abstraction at all. It's pure PIL/EXIF parsing and
belongs with the other generic helpers, not squatting in the executors file.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# EXIF tag numbers → friendly names.
_EXIF_TAGS = {
    271: "camera_make",
    272: "camera_model",
    274: "orientation",
    306: "datetime",
    36867: "datetime_original",
}

# The GPS IFD lives under EXIF tag 0x8825; within it these sub-tags carry coords.
_GPS_IFD_TAG = 0x8825
_GPS_LAT_REF, _GPS_LAT, _GPS_LON_REF, _GPS_LON = 1, 2, 3, 4

# Shutter/aperture/ISO/focal length/lens live in the Exif SubIFD (tag 0x8769), not
# the main IFD0 — a separate sub-dict, same as GPS.
_EXIF_SUBIFD_TAG = 0x8769
_EXIF_SUBIFD_TAGS = {
    33434: "exposure_time",
    33437: "f_number",
    34855: "iso",
    37386: "focal_length",
    42036: "lens_model",
}


def _to_number(value: Any) -> Any:
    """Coerce a PIL IFDRational to a plain float; passes through anything else unchanged."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return value


def _exif_subifd_to_dict(raw: dict[int, Any]) -> dict[str, Any]:
    """Map the Exif SubIFD (shutter/aperture/ISO/focal length/lens) to named fields."""
    result: dict[str, Any] = {}
    for tag, name in _EXIF_SUBIFD_TAGS.items():
        value = raw.get(tag)
        if value in (None, ""):
            continue
        result[name] = value.strip() if isinstance(value, str) else _to_number(value)
    return result


def _exif_to_dict(raw: dict[int, Any]) -> dict[str, Any]:
    """Map a raw EXIF tag→value dict (from PIL ``getexif``) to named fields."""
    result: dict[str, Any] = {}
    for tag, name in _EXIF_TAGS.items():
        value = raw.get(tag)
        if value in (None, ""):
            continue
        result[name] = value.strip() if isinstance(value, str) else value
    return result


def _dms_to_decimal(coord: Any, ref: Any) -> float | None:
    """Convert an EXIF (degrees, minutes, seconds) rational triple to signed decimal."""
    try:
        degrees, minutes, seconds = (float(x) for x in coord)
    except (TypeError, ValueError):
        return None
    value = degrees + minutes / 60.0 + seconds / 3600.0
    if str(ref).upper() in ("S", "W"):
        value = -value
    return round(value, 6)


def _gps_to_dict(gps_ifd: dict[int, Any]) -> dict[str, Any]:
    """Extract decimal lat/long from an EXIF GPS IFD, if present and valid."""
    result: dict[str, Any] = {}
    lat = _dms_to_decimal(gps_ifd.get(_GPS_LAT), gps_ifd.get(_GPS_LAT_REF))
    lon = _dms_to_decimal(gps_ifd.get(_GPS_LON), gps_ifd.get(_GPS_LON_REF))
    if lat is not None:
        result["gps_latitude"] = lat
    if lon is not None:
        result["gps_longitude"] = lon
    return result


def extract_image_metadata(path: str | Path) -> dict[str, Any]:
    """Read dimensions + EXIF (incl. GPS) straight from the original file on disk.

    Reading from ``path`` — not from a possibly-transformed in-memory image — means
    the result never depends on where metadata extraction sits relative to resize /
    grayscale nodes. Missing or malformed EXIF degrades gracefully to just size.
    """
    from PIL import Image

    with Image.open(path) as image:
        width, height = image.size
        meta: dict[str, Any] = {"width": width, "height": height}
        try:
            exif = image.getexif()
        except Exception:
            return meta
        if not exif:
            return meta
        meta.update(_exif_to_dict(dict(exif)))
        try:
            gps_ifd = exif.get_ifd(_GPS_IFD_TAG)
        except Exception:
            gps_ifd = None
        if gps_ifd:
            meta.update(_gps_to_dict(dict(gps_ifd)))
        try:
            sub_ifd = exif.get_ifd(_EXIF_SUBIFD_TAG)
        except Exception:
            sub_ifd = None
        if sub_ifd:
            meta.update(_exif_subifd_to_dict(dict(sub_ifd)))
    return meta
