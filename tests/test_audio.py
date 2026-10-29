import io
import math
import struct
import wave

from core.audio import wav_to_mp3


def _wav(rate=44100, channels=1, seconds=1.0):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        n = int(rate * seconds)
        w.writeframes(b"".join(struct.pack("<h", int(3000 * math.sin(2 * math.pi * 440 * t / rate))) * channels for t in range(n)))
    return buf.getvalue()


def test_wav_becomes_mp3():
    mp3 = wav_to_mp3(_wav())
    assert not mp3.startswith(b"RIFF")
    assert mp3[:3] == b"ID3" or (mp3[0] == 0xFF and mp3[1] & 0xE0 == 0xE0)  # MP3 frame sync
    assert len(mp3) > 1000


def test_stereo_wav_is_accepted():
    assert len(wav_to_mp3(_wav(rate=48000, channels=2))) > 1000
