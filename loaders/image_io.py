"""OME-TIFF reading and lightweight display helpers for Step3.1."""

import os
import numpy as np
import tifffile
import zarr

from configs.defaults import MAX_OVERVIEW_SIDE


def read_ome_2d(path):
    """Return a 2D array from an OME-TIFF-like file."""
    arr = tifffile.imread(path)
    arr = np.asarray(arr)
    arr = np.squeeze(arr)
    if arr.ndim > 2:
        arr = arr.reshape((-1,) + arr.shape[-2:])[0]
    return arr


def read_ome_region(path, y0, y1, x0, x1, stride=1):
    """Read a 2D ROI-local crop from an OME-TIFF-like file."""
    try:
        arr = tifffile.memmap(path)
        arr = np.asarray(arr)
    except Exception:
        arr = tifffile.imread(path)
    arr = np.asarray(arr)
    arr = np.squeeze(arr)
    if arr.ndim > 2:
        arr = arr.reshape((-1,) + arr.shape[-2:])[0]
    return np.asarray(arr[int(y0):int(y1):int(stride), int(x0):int(x1):int(stride)])


def overview_stride(shape, max_side=MAX_OVERVIEW_SIDE):
    h, w = int(shape[0]), int(shape[1])
    return max(1, int(np.ceil(max(h, w) / float(max_side))))


def downsample_view(arr, stride):
    if stride <= 1:
        return arr
    return arr[::stride, ::stride]


def _zarr_array(root):
    if hasattr(root, "ndim"):
        return root
    if hasattr(root, "keys"):
        keys = list(root.keys())
        if "0" in keys:
            try:
                return root[0]
            except Exception:
                return root["0"]
        if keys:
            return root[keys[0]]
    return root


def read_ome_channel_region(path, channel_index, y0, y1, x0, x1, stride=1):
    """Read a 2D channel crop from OME-TIFF through tifffile zarr."""
    tif = tifffile.TiffFile(path)
    store = tif.aszarr()
    try:
        z0 = _zarr_array(zarr.open(store, mode="r"))
        if z0.ndim == 4:
            arr = z0[0, channel_index, y0:y1:stride, x0:x1:stride]
        elif z0.ndim == 3:
            arr = z0[channel_index, y0:y1:stride, x0:x1:stride]
        elif z0.ndim == 2:
            arr = z0[y0:y1:stride, x0:x1:stride]
        else:
            raise RuntimeError(f"Unsupported OME-TIFF dimensions: {z0.shape}")
        return np.asarray(arr)
    finally:
        store.close()
        tif.close()


def zarr_group_names(path):
    """Return top-level array/group names from a zarr store."""
    if not path:
        return []
    root = zarr.open(path, mode="r")
    if not hasattr(root, "keys"):
        return []
    return sorted(str(k) for k in root.keys())


def read_zarr_channel(path, channel_name, roi_name=None, y0=0, y1=None, x0=0, x1=None, stride=1):
    """Read a channel crop from corrected_channels.zarr style stores."""
    root = zarr.open(path, mode="r")
    arr = None
    if roi_name and roi_name in root and channel_name in root[roi_name]:
        arr = root[roi_name][channel_name]
    elif channel_name in root:
        arr = root[channel_name]
    if arr is None:
        raise KeyError(f"Channel not found: {channel_name}")
    y1 = arr.shape[0] if y1 is None else y1
    x1 = arr.shape[1] if x1 is None else x1
    return np.asarray(arr[y0:y1:stride, x0:x1:stride])


def list_corrected_channels(path, roi_names=()):
    if not path or not os.path.exists(path):
        return []
    root = zarr.open(path, mode="r")
    if not hasattr(root, "keys"):
        return []
    for roi_name in roi_names:
        if roi_name and roi_name in root and hasattr(root[roi_name], "keys"):
            return sorted(str(k) for k in root[roi_name].keys())
    return sorted(str(k) for k in root.keys() if hasattr(root[k], "shape"))


def read_fusion_region(path, y0, y1, x0, x1, stride=1):
    if not path or not os.path.exists(path):
        return None
    z = zarr.open(path, mode="r")
    if not hasattr(z, "shape") or len(z.shape) < 3:
        return None
    patch = np.asarray(z[int(y0):int(y1):int(stride), int(x0):int(x1):int(stride), :])
    if patch.ndim != 3:
        return None
    if patch.shape[2] == 2:
        rgb = np.zeros(patch.shape[:2] + (3,), dtype=np.uint8)
        rgb[..., 0] = normalize_u8(patch[..., 0])
        rgb[..., 2] = normalize_u8(patch[..., 1])
        return rgb
    chans = [normalize_u8(patch[..., i]) for i in range(min(3, patch.shape[2]))]
    while len(chans) < 3:
        chans.append(np.zeros_like(chans[0]))
    return np.stack(chans[:3], axis=-1)


def read_raw_ome_channel_region(raw_ome, channel_name, global_bbox, stride=1):
    from block01.core.io_loader import OMETIFFLoader

    loader = OMETIFFLoader(raw_ome)
    y0, y1, x0, x1 = [int(v) for v in global_bbox]
    return loader.read_region(
        channel_name,
        y0,
        y1,
        x0,
        x1,
        downsample=int(stride),
        normalize=False,
    )


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


def normalize_float(arr, p_low=1.0, p_high=99.5):
    u8 = normalize_u8(arr, p_low=p_low, p_high=p_high)
    return u8.astype(np.float32) / 255.0


def dapi_rgb(arr, intensity=1.0):
    u8 = normalize_u8(arr)
    scale = float(np.clip(intensity, 0.0, 3.0))
    blue = np.clip(u8.astype(np.float32) * scale, 0, 255).astype(np.uint8)
    rgb = np.zeros(u8.shape + (3,), dtype=np.uint8)
    rgb[..., 2] = blue
    rgb[..., 0] = (blue.astype(np.float32) * 0.18).astype(np.uint8)
    rgb[..., 1] = (blue.astype(np.float32) * 0.34).astype(np.uint8)
    return rgb


def compose_overlay_rgb(
    dapi,
    fusion=None,
    marker_layers=None,
    dapi_visible=True,
    fusion_visible=False,
    dapi_intensity=1.0,
    fusion_intensity=1.0,
):
    """Compose DAPI, optional fusion, and marker overlays into RGB uint8."""
    base_shape = np.asarray(dapi).shape[:2]
    canvas = np.zeros(base_shape + (3,), dtype=np.float32)
    if dapi_visible:
        canvas += dapi_rgb(dapi, intensity=dapi_intensity).astype(np.float32) / 255.0
    if fusion_visible and fusion is not None:
        f = np.asarray(fusion)
        if f.ndim == 3 and f.shape[2] >= 3:
            frgb = f.astype(np.float32)
            if frgb.max(initial=0) > 1.0:
                frgb /= 255.0
            canvas += frgb[:, :, :3] * float(np.clip(fusion_intensity, 0.0, 3.0))
        else:
            norm = normalize_float(f)
            canvas[:, :, 0] += norm * float(np.clip(fusion_intensity, 0.0, 3.0))
            canvas[:, :, 1] += norm * 0.5 * float(np.clip(fusion_intensity, 0.0, 3.0))
    for layer in marker_layers or []:
        arr = layer.get("array")
        if arr is None:
            continue
        color = np.asarray(layer.get("color", (255, 255, 255)), dtype=np.float32) / 255.0
        alpha = float(np.clip(layer.get("alpha", 0.65), 0.0, 1.0))
        norm = normalize_float(arr, layer.get("p_low", 1.0), layer.get("p_high", 99.5))
        canvas += norm[:, :, None] * color[None, None, :] * alpha
    return np.clip(canvas * 255.0, 0, 255).astype(np.uint8)


def mask_outline(mask):
    m = np.asarray(mask)
    if m.ndim > 2:
        m = np.squeeze(m)
    if m.size == 0:
        return np.zeros(m.shape, dtype=bool)
    try:
        from cellpose import utils as cellpose_utils

        return np.asarray(cellpose_utils.masks_to_outlines(m.astype(np.int32)), dtype=bool)
    except Exception:
        pass
    fg = m > 0
    out = np.zeros(fg.shape, dtype=bool)
    out[1:, :] |= fg[1:, :] != fg[:-1, :]
    out[:-1, :] |= fg[1:, :] != fg[:-1, :]
    out[:, 1:] |= fg[:, 1:] != fg[:, :-1]
    out[:, :-1] |= fg[:, 1:] != fg[:, :-1]
    return out


def outline_rgba(mask, color, width=1):
    outline = mask_outline(mask)
    width = float(width)
    if width > 1.0:
        try:
            from scipy import ndimage as ndi

            outline = ndi.binary_dilation(outline, iterations=max(1, int(round(width)) - 1))
        except Exception:
            pass
    rgba = np.zeros(outline.shape + (4,), dtype=np.uint8)
    rgba[outline, 0] = int(color[0])
    rgba[outline, 1] = int(color[1])
    rgba[outline, 2] = int(color[2])
    rgba[outline, 3] = int(150 * max(0.35, min(1.0, width)))
    return rgba


def mask_fill_rgba(mask, color, alpha=0.0):
    m = np.asarray(mask) > 0
    rgba = np.zeros(m.shape + (4,), dtype=np.uint8)
    rgba[m, 0] = int(color[0])
    rgba[m, 1] = int(color[1])
    rgba[m, 2] = int(color[2])
    rgba[m, 3] = int(np.clip(alpha, 0.0, 1.0) * 180)
    return rgba
