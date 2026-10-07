"""Turns narration lines into WAV files with Kokoro, a free AI voice that runs on this computer (no internet needed).

Called by record.mjs:  speak_kokoro.py --json lines.json --out folder [--voice af_heart] [--speed 1.0]
Writes <key>.wav for every key in the JSON file.

One-time setup (see docs/DEMO.md): a Python environment with `kokoro-onnx` and `soundfile`, plus the two model
files kokoro-v1.0.onnx and voices-v1.0.bin, all in one folder (default ~/algo-kokoro, or set KOKORO_HOME).
Run this with the Python from that folder's venv.
"""

import argparse
import json
import os
from pathlib import Path

import soundfile
from kokoro_onnx import Kokoro

parser = argparse.ArgumentParser()
parser.add_argument("--json", required=True)
parser.add_argument("--out", required=True)
parser.add_argument("--voice", default="af_heart")
parser.add_argument("--speed", type=float, default=1.0)
args = parser.parse_args()

home = Path(os.environ.get("KOKORO_HOME") or Path.home() / "algo-kokoro")
kokoro = Kokoro(str(home / "kokoro-v1.0.onnx"), str(home / "voices-v1.0.bin"))

lines = json.loads(Path(args.json).read_text(encoding="utf-8-sig"))
for key, text in lines.items():
    samples, rate = kokoro.create(text, voice=args.voice, speed=args.speed, lang="en-us")
    soundfile.write(str(Path(args.out) / f"{key}.wav"), samples, rate)
