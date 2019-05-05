import logging
import subprocess

import cv2
import numpy as np

_LG = logging.getLogger(__name__)


def load_image(path, resize=None):
    """Load image from file into CHW-RGB within [-1.0, 1.0]

    Parameters
    ----------
    resize : tuple of int
        (weight, height)
    """
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        raise RuntimeError('Failed to load image; %s' % path)
    # BGR -> RGB
    img = img[:, :, ::-1]
    if resize:
        img = cv2.resize(img, resize)
    img = 2 * (img.astype('float') / 255) - 1.0
    # (H, W, C) -> (C, H, W)
    img = img.transpose((2, 0, 1))
    return img


def save_image(img, path):
    """Save image to file"""
    # (C, H, W) -> (H, W, C)
    img = img.transpose((1, 2, 0))
    # RGB -> BGR
    img = img[:, :, ::-1]
    img = 255 * (img + 1.0) / 2
    img = img.clip(min=0, max=255).astype('uint8')
    cv2.imwrite(path, img)


def _prod(vals):
    ret = 1
    for val in vals:
        ret *= val
    return ret


class VideoLoader:
    def __init__(self, path, scale, frame_rate=30, debug=False):
        self.path = path
        self.scale = scale
        self.frame_rate = frame_rate
        self.debug = debug
        self.process = None

    def __enter__(self):
        width, height = self.scale
        command = [
            'ffmpeg',
            '-hide_banner',
            '-i', self.path,
            '-f', 'rawvideo',
            '-r', str(self.frame_rate),
            '-pix_fmt', 'rgb24',
            '-vf', 'scale=%d:%d' % (width, height),
            '-',
        ]
        frame_size = 3 * width * height
        self.process = subprocess.Popen(
            args=command,
            stdout=subprocess.PIPE,
            stderr=None if self.debug else subprocess.DEVNULL,
            bufsize=32*frame_size,
        )
        return self

    def __exit__(self, *args):
        returncode = self.process.wait(timeout=3)
        if returncode != 0:
            _LG.error(
                'Key frame decoding process (ffmpeg) did not '
                'complete correctly. Return code: %s', returncode
            )
        self.process = None

    def __iter__(self):
        width, height = self.scale
        shape = (height, width, 3)
        frame_size = _prod(shape)
        n_yield = 0
        while True:
            val = self.process.stdout.read(frame_size)
            if len(val) != frame_size:
                break
            frame = np.frombuffer(val, dtype='uint8')
            frame = frame.reshape(shape).transpose(2, 0, 1)
            yield frame
            n_yield += 1
        _LG.info('Finished key frame extraction: %d extracted.', n_yield)


class VideoSaver:
    def __init__(self, path, scale, frame_rate=30, debug=False):
        self.path = path
        self.scale = scale
        self.frame_rate = frame_rate
        self.debug = debug
        self.process = None

    def __enter__(self):
        width, height = self.scale
        command = [
            'ffmpeg',
            '-hide_banner', '-y',
            '-f', 'rawvideo',
            '-vcodec', 'rawvideo',
            '-framerate', str(self.frame_rate),
            '-s', '%dx%d' % (width, height),
            '-pix_fmt', 'rgb24',
            '-i', '-',
            '-an',
            '-codec:v', 'libx264',
            '-preset', 'veryslow',
        ]
        if width % 2 == 0 and height % 2 == 0:
            command += ['-pix_fmt', 'yuv420p']
        command += [self.path]
        _LG.debug(command)
        frame_size = 3 * width * height
        self.process = subprocess.Popen(
            args=command,
            stdin=subprocess.PIPE,
            stdout=None if self.debug else subprocess.DEVNULL,
            stderr=None if self.debug else subprocess.DEVNULL,
            bufsize=frame_size,
        )
        return self

    def __exit__(self, *args):
        self.process.stdin.close()
        self.process.wait(3)

    def write(self, frame):
        self.process.stdin.write(frame)

    def flush(self):
        self.process.stdin.flush()