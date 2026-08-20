#!/usr/bin/env python3

from pathlib import Path
import shutil

src_dir = Path("assets")
target_dir = Path("build/liveability/ios/xcode/Support/Python.xcframework/ios-arm64/lib-arm64/python3.14/lib-dynload")

mapping = { "_hashlib": "OpenSSL", "_ssl": "OpenSSL" }

for k, v in mapping.items():
    if not (target := (target_dir / f"{k}.xcprivacy")).exists() and (src := (src_dir / f"{v}.xcprivacy")).exists():
        shutil.copy(src, target)
