# SPDX-License-Identifier: AGPL-3.0-or-later
"""Reproducibly convert the official Real-ESRGAN realesr-general-x4v3 weights to ONNX.

Weights: https://github.com/xinntao/Real-ESRGAN (BSD-3-Clause, Copyright (c) 2021 Xintao Wang).
Run (no GPU needed), from the repo root:

  docker run --rm -v "$PWD:/w" -w /w python:3.12-slim sh -c \
    "pip install -q torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu && \
     pip install -q onnx==1.23.2 onnxruntime==1.32.0 && \
     python scripts/convert_realesrgan.py /w/<dir-with-pth> backend/app/upscale"

The architecture below (SRVGGNetCompact) is written from the published layer layout so the
official state dict loads unchanged; the exported graph is checked against PyTorch.
"""

import hashlib
import sys
from pathlib import Path

import numpy as np
import onnxruntime as ort
import torch
from torch import nn
from torch.nn import functional as F  # noqa: N812


class SRVGGNetCompact(nn.Module):
    def __init__(self, num_feat=64, num_conv=32, upscale=4):
        super().__init__()
        self.upscale = upscale
        layers: list[nn.Module] = [nn.Conv2d(3, num_feat, 3, 1, 1), nn.PReLU(num_parameters=num_feat)]
        for _ in range(num_conv):
            layers += [nn.Conv2d(num_feat, num_feat, 3, 1, 1), nn.PReLU(num_parameters=num_feat)]
        layers.append(nn.Conv2d(num_feat, 3 * upscale * upscale, 3, 1, 1))
        self.body = nn.ModuleList(layers)
        self.upsampler = nn.PixelShuffle(upscale)

    def forward(self, x):
        out = x
        for layer in self.body:
            out = layer(out)
        out = self.upsampler(out)
        return out + F.interpolate(x, scale_factor=self.upscale, mode="nearest")


def main(src_dir: str, out_dir: str) -> None:
    pth = Path(src_dir) / "realesr-general-x4v3.pth"
    state = torch.load(pth, map_location="cpu", weights_only=True)  # no pickle code execution
    state = state.get("params", state)
    model = SRVGGNetCompact().eval()
    model.load_state_dict(state, strict=True)

    out = Path(out_dir) / "realesr-general-x4v3.onnx"
    dummy = torch.rand(1, 3, 64, 64)
    torch.onnx.export(
        model, dummy, out, input_names=["input"], output_names=["output"], opset_version=17,
        dynamic_axes={"input": {2: "h", 3: "w"}, "output": {2: "H", 3: "W"}}, dynamo=False,
    )
    probe = torch.rand(1, 3, 96, 80)
    with torch.no_grad():
        ref = model(probe).numpy()
    got = ort.InferenceSession(str(out)).run(None, {"input": probe.numpy()})[0]
    diff = float(np.abs(ref - got).max())
    print("max abs diff torch vs onnx:", diff)
    assert diff < 1e-3, diff
    print("sha256(pth):", hashlib.sha256(pth.read_bytes()).hexdigest())
    print("sha256(onnx):", hashlib.sha256(out.read_bytes()).hexdigest())


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
