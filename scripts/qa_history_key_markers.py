"""Inspect historical PEM markers without displaying credential content."""

import json
import re
import subprocess
from pathlib import Path

from cryptography.hazmat.primitives.serialization import load_pem_private_key

root = Path(__file__).resolve().parents[1]
command = ["git", "-c", f"safe.directory={root.as_posix()}"]
reports = []
for name in ("creation", "drive", "sheets", "stabilization"):
    path = f"design-work/qa/validation-{name}-regression.xml"
    if name == "stabilization":
        path = "design-work/qa/validation-stabilization.xml"
    data = subprocess.check_output([*command, "show", f"HEAD:{path}"], cwd=root)
    blocks = re.findall(
        rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----.*?"
        rb"-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", data, re.DOTALL
    )
    valid = 0
    for block in blocks:
        try:
            load_pem_private_key(block, None)
            valid += 1
        except (ValueError, TypeError):
            pass
    reports.append({"path": path, "complete_blocks": len(blocks), "parsable_keys": valid,
                    "known_test_canary": b"FAKE_CANARY_NOT_A_SECRET" in data,
                    "incomplete_marker_count": data.count(b"-----BEGIN " + b"PRIVATE KEY-----")
                    - len(blocks)})
print(json.dumps(reports))
