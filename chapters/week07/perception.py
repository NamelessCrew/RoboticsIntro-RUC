"""受控红色方块的 RGB-D 定位。颜色阈值不是语义检测/YOLO。"""
import numpy as np


def pixel_to_world(u, v, depth_m, K, T_world_camera_cv):
    if not np.isfinite([u, v, depth_m]).all() or depth_m <= 0:
        raise ValueError("pixel/depth must be finite and depth positive")
    camera = np.linalg.solve(np.asarray(K), np.array([u, v, 1.]))*depth_m
    T = np.asarray(T_world_camera_cv)
    return T[:3, :3] @ camera + T[:3, 3]


def locate_red_cube(rgb, depth_m, calibration, half_height=.02):
    """使用 RGB 掩码选像素，再以度量深度反投影；已知半高补偿顶面到中心。

    不读取物体姿态或 MuJoCo segmentation。仅适用于一个红色、平放、无遮挡方块。
    """
    rgb = np.asarray(rgb, float)
    depth_m = np.asarray(depth_m)
    if rgb.ndim != 3 or rgb.shape[2] != 3 or depth_m.shape != rgb.shape[:2]:
        raise ValueError("RGB and depth shapes do not match")
    mask = (rgb[..., 0] > 70) & (rgb[..., 0] > 1.8*rgb[..., 1]) & (rgb[..., 0] > 1.8*rgb[..., 2])
    mask &= np.isfinite(depth_m) & (depth_m > .05) & (depth_m < 3)
    v, u = np.nonzero(mask)
    if len(u) < 9:
        raise ValueError("Red cube not detected: fewer than 9 valid pixels")
    K, T = calibration["K"], calibration["T_world_camera_cv"]
    rays = np.linalg.solve(K, np.stack([u, v, np.ones(len(u))]))
    camera = rays*depth_m[v, u]
    world = (T[:3, :3] @ camera + T[:3, 3, None]).T
    # 俯视相机中多数掩码像素属于顶面。中位数抑制边缘和阴影。
    surface = np.median(world, axis=0)
    center = surface - [0, 0, half_height]
    return center, {"method": "red_color_mask_rgbd", "pixels": len(u),
                    "bbox_xyxy": [int(u.min()), int(v.min()), int(u.max()), int(v.max())],
                    "center_pixel_uv": [float(np.median(u)), float(np.median(v))],
                    "surface_world_m": surface.tolist(), "known_half_height_m": half_height}
