> Review (2026-11-17): every runtime dependency is under a permissive licence (MIT, BSD, Apache-2.0,
> ISC, PSF, 0BSD, Unlicense, MIT-CMU) except **certifi (MPL-2.0)**, a file-level weak copyleft
> licence. We use certifi unmodified as a transitive dependency of httpx, which MPL-2.0 permits and
> which is compatible with AGPL-3.0. If you modify certifi's files, publish those modifications.
> Fonts: none bundled (system font stack). Icons/logo: drawn for this project.
> Bundled model: Real-ESRGAN realesr-general-x4v3 weights (BSD-3-Clause, (c) 2021 Xintao Wang),
> notice in backend/app/upscale/LICENSE-Real-ESRGAN. Demo clip: our own render (AGPL).
