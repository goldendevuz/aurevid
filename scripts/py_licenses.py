# SPDX-License-Identifier: AGPL-3.0-or-later
"""Print a markdown table of installed distributions and their license metadata.

Order of evidence: PEP 639 License-Expression, then the License field (short values only),
then Trove classifiers. Anything else is reported as UNKNOWN for manual review.
"""

from importlib.metadata import distributions

rows = {}
for dist in distributions():
    meta = dist.metadata
    name = meta["Name"]
    if not name or name.lower() in {"pip", "setuptools", "wheel"}:
        continue
    lic = meta.get("License-Expression")
    if not lic:
        raw = (meta.get("License") or "").strip()
        if raw and "\n" not in raw and len(raw) < 60:
            lic = raw
    if not lic:
        classifiers = [
            c.split("::")[-1].strip()
            for c in meta.get_all("Classifier") or []
            if c.startswith("License ::") and "OSI Approved" in c and c.count("::") > 1
        ]
        lic = " / ".join(classifiers) if classifiers else "UNKNOWN"
    rows[name.lower()] = (name, dist.version, lic)

print("| Name | Version | License |")
print("|------|---------|---------|")
for _, (name, version, lic) in sorted(rows.items()):
    print(f"| {name} | {version} | {lic} |")
