"""逐帧流式写 H.264 MP4；不在内存积累整段图像，未完成视频明确保留 partial 名称。"""
from pathlib import Path

import imageio_ffmpeg
import numpy as np


class TaskVideo:
    def __init__(self, output, enabled=True, fps=10, size=(512, 512)):
        self.output = Path(output)
        self.enabled, self.fps, self.size = enabled, fps, size
        self.partial = self.output/"grasp.partial.mp4"
        self.final = self.output/"grasp.mp4"
        self.writer = None
        self.frames = 0
        self.next_time = 0.
        self.last_time = 0.
        self.status = "not_started" if enabled else "disabled"
        self.encoder_error = None

    def __enter__(self):
        return self

    def capture(self, env):
        if not self.enabled or float(env.data.time)+1e-8 < self.next_time:
            return
        frame = env.render("demo", resolution=self.size)
        if self.writer is None:
            self.output.mkdir(parents=True, exist_ok=True)
            self.writer = imageio_ffmpeg.write_frames(str(self.partial), self.size, fps=self.fps,
                codec="libx264", pix_fmt_out="yuv420p", quality=7,
                output_params=["-movflags", "+faststart"], ffmpeg_log_level="error", ffmpeg_timeout=10)
            self.writer.send(None)
        self.writer.send(np.ascontiguousarray(frame, dtype=np.uint8).tobytes())
        self.frames += 1
        self.last_time = float(env.data.time)
        self.next_time += 1/self.fps
        self.status = "recording"

    def __exit__(self, exc_type, *_):
        if self.writer is None:
            return
        try:
            self.writer.close()
            if exc_type is None:
                self.partial.replace(self.final)
                self.status = "completed"
            else:
                self.status = "partial"
        except Exception as error:
            self.encoder_error = str(error)
            self.status = "encoding_failed"
            if exc_type is None:
                raise
        finally:
            self.writer = None

    def metadata(self):
        path = self.final if self.status == "completed" else self.partial
        return {"status": self.status, "path": path.name if self.frames and path.is_file() else None,
                "fps": self.fps, "frame_count": self.frames,
                "duration_s": self.frames/self.fps, "last_frame_sim_time_s": self.last_time,
                "encoder_error": self.encoder_error}
