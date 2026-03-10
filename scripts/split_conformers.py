# -*- coding: utf-8 -*-
"""

@author: Abhinav Abraham

"""

from pathlib import Path

def run(cfg, dirs, logger, multi_xyz: Path):
    outdir = dirs["confs"]
    marker = outdir / ".split_done"

    if marker.exists():
        logger.info("[split] SKIP: %s exists", marker)
        return outdir

    lines = multi_xyz.read_text(errors="ignore").splitlines()
    i = 0
    k = 0
    while i < len(lines):
        if not lines[i].strip():
            i += 1
            continue
        n = int(lines[i].split()[0])
        frame = lines[i:i+2+n]
        k += 1
        (outdir / f"c{k:04d}.xyz").write_text("\n".join(frame).rstrip() + "\n")
        i += 2 + n

    marker.write_text(f"{k}\n")
    logger.info("[split] WROTE %d conformers into %s", k, outdir)
    return k