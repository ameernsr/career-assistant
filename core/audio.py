"""A-10: browser microphones record WAV, but the gateway's speech-to-text only accepts compressed audio (WAV → HTTP 400)."""
import io
import wave

import lameenc
import numpy as np


def wav_to_mp3(wav: bytes, bitrate_kbps: int = 64) -> bytes:
    with wave.open(io.BytesIO(wav), "rb") as w:
        channels, width, rate = w.getnchannels(), w.getsampwidth(), w.getframerate()
        frames = w.readframes(w.getnframes())
    if width == 1:  # 8-bit unsigned → 16-bit signed
        pcm = ((np.frombuffer(frames, dtype=np.uint8).astype(np.int16) - 128) << 8).tobytes()
    elif width == 4:
        pcm = (np.frombuffer(frames, dtype=np.int32) >> 16).astype(np.int16).tobytes()
    else:
        pcm = frames
    enc = lameenc.Encoder()
    enc.set_bit_rate(bitrate_kbps)
    enc.set_in_sample_rate(rate)
    enc.set_channels(channels)
    enc.set_quality(5)
    return bytes(enc.encode(pcm) + enc.flush())
