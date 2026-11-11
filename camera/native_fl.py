"""Apply/restore the bounded FL-inspired LUT through the verified lab transport."""
import json
import os
from pathlib import Path

from camera.lut_probe import Bundle
from local import require
from research.native_fl import Codec, KIND, build_table


class NativeFL(Bundle):
    kind = KIND
    prefix = 'LIVE_NATIVE_FL_'

    def __init__(self, path, apply=False):
        self.codec = Codec((path/'codec.bin').read_bytes())
        self.recipe = json.loads((path/'recipe.json').read_text())
        super().__init__(path, apply=apply)

    def build_candidate(self, original):
        return build_table(original, self.codec, self.recipe)


def configured(apply=False):
    path = os.environ.get('A7M3_LUT_EXPERIMENT')
    require(bool(path), 'Set A7M3_LUT_EXPERIMENT to the prepared FL bundle')
    return NativeFL(Path(path).expanduser().resolve(), apply=apply)


def perform(camera, operation):
    configured(apply=operation == 'apply').operate(camera, operation)
