"""OME-TIFF reading and lightweight display helpers for Step3.1."""

import numpy as np
import tifffile

from configs.defaults import MAX_OVERVIEW_SIDE


def read_ome_2d(path):
    """Return a 2D array from an OME-TIFF-like file."""
    arr = tifffile.imread(path)
    arr = np.asarray(arr)
    arr = np.squeeze(arr)
    if arr.ndim > 2:
        arr = arr.reshape((-1,) + arr.shape[-2:])[0]
    return arr


def overview_stride(shape, max_side=MAX_OVERVIEW_SIDE):
    h, w = int(shape[0]), int(shape[1])
    return max(1, int(np.ceil(max(h, w) / float(max_side))))


def downsample_view(arr, stride):
    if stride <= 1:
        return arr
    return arr[::stride, ::stride]


def normalize_u8(arr, p_low=1.0, p_high=99.5):
    a = np.asarray(arr, dtype=np.float32)
    finite = a[np.isfinite(a)]
    if finite.size == 0:
        return np.zeros(a.shape, dtype=np.uint8)
    lo, hi = np.percentile(finite, [p_low, p_high])
    if hi <= lo:
        hi = float(finite.max()) if finite.size else 1.0
        lo = float(finite.min()) if finite.size else 0.0
        if hi <= lo:
            return np.zeros(a.shape, dtype=np.uint8)
    out = np.clip((a - lo) / (hi - lo), 0.0, 1.0)
    return (out * 255.0).astype(np.uint8)


def dapi_rgb(arr, intensity=1.0):
    u8 = normalize_u8(arr)
    scale = float(np.clip(intensity, 0.0, 3.0))
    blue = np.clip(u8.astype(np.float32) * scale, 0, 255).astype(np.uint8)
    rgb = np.zeros(u8.shape + (3,), dtype=np.uint8)
    rgb[..., 2] = blue
    rgb[..., 0] = (blue.astype(np.float32) * 0.18).astype(np.uint8)
    rgb[..., 1] = (blue.astype(np.float32) * 0.34).astype(np.uint8)
    return rgb


def mask_outline(mask):
    m = np.asarray(mask)
    if m.ndim > 2:
        m = np.squeeze(m)
    if m.size == 0:
        return np.zeros(m.shape, dtype=bool)
    fg = m > 0
    out = np.zeros(fg.shape, dtype=bool)
    out[1:, :] |= fg[1:, :] != fg[:-1, :]
    out[:-1, :] |= fg[1:, :] != fg[:-1, :]
    out[:, 1:] |= fg[:, 1:] != fg[:, :-1]
    out[:, :-1] |= fg[:, 1:] != fg[:, :-1]
    return out


def outline_rgba(mask, color, width=1):
    outline = mask_outline(mask)
    if width > 1:
        try:
            from scipy import ndimage as ndi

            outline = ndi.binary_dilation(outline, iterations=int(width) - 1)
        except Exception:
            pass
    rgba = np.zeros(outline.shape + (4,), dtype=np.uint8)
    rgba[outline, 0] = int(color[0])
    rgba[outline, 1] = int(color[1])
    rgba[outline, 2] = int(color[2])
    rgba[outline, 3] = 230
    return rgba
