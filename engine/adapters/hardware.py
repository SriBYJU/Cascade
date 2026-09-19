from __future__ import annotations

import os
import platform
import shutil
from dataclasses import dataclass

from ..tools.runner import run_command


@dataclass(slots=True)
class HardwareInfo:
    system: str
    machine: str
    cpu_count: int
    ram_bytes: int | None
    gpu_summary: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "system": self.system,
            "machine": self.machine,
            "cpu_count": self.cpu_count,
            "ram_bytes": self.ram_bytes,
            "gpu_summary": self.gpu_summary,
        }


def detect_hardware() -> HardwareInfo:
    ram: int | None = None
    try:
        if hasattr(os, "sysconf"):
            ram = int(os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE"))
    except (ValueError, OSError):
        pass
    gpu: str | None = None
    if shutil.which("nvidia-smi"):
        result = run_command(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            ".",
            timeout_seconds=5,
            output_cap_chars=2000,
        )
        if result.exit_code == 0:
            gpu = result.stdout.strip()
    return HardwareInfo(platform.system(), platform.machine(), os.cpu_count() or 1, ram, gpu)
