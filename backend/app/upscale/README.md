# Upscaling model

`realesr-general-x4v3.onnx` is the official Real-ESRGAN **realesr-general-x4v3** checkpoint
(https://github.com/xinntao/Real-ESRGAN, release v0.2.5.0), converted to ONNX with
`scripts/convert_realesrgan.py`. Licence: BSD-3-Clause, see `LICENSE-Real-ESRGAN`
(Copyright (c) 2021, Xintao Wang). Not modified apart from the format conversion.

| File | SHA-256 |
|---|---|
| realesr-general-x4v3.pth (source) | `8dc7edb9ac80ccdc30c3a5dca6616509367f05fbc184ad95b731f05bece96292` |
| realesr-general-x4v3.onnx | `41bc536cbf3ed84ce5612ee1708a25c27c3a48e90d48d7fe33f061f8602570a2` |

Conversion check: PyTorch vs ONNX Runtime max absolute difference 9.5e-7 (torch 2.15.0+cpu,
onnx 1.23.2, onnxruntime 1.32.0). The state dict loaded with `strict=True`.
