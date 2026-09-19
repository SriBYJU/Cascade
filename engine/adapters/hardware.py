from __future__ import annotations

import ctypes
import os
import platform
import shutil
import subprocess
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


def _ram_bytes() -> int | None:
    system = platform.system()
    try:
        if system == "Windows":
            class MemoryStatus(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = MemoryStatus()
            status.dwLength = ctypes.sizeof(MemoryStatus)
            windll = getattr(ctypes, "windll", None)
            if windll is None:
                return None
            kernel32 = windll.kernel32
            if kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return int(status.ullTotalPhys)
            return None
        if system == "Darwin" and shutil.which("sysctl"):
            proc = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                text=True,
                capture_output=True,
                timeout=5,
                check=False,
            )
            raw = proc.stdout.strip()
            return int(raw) if proc.returncode == 0 and raw.isdigit() else None
        if hasattr(os, "sysconf"):
            pages = os.sysconf("SC_PHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")
            return int(pages * page_size)
    except (AttributeError, OSError, TypeError, ValueError, subprocess.TimeoutExpired):
        return None
    return None


def _gpu_summary() -> str | None:
    executable = shutil.which("nvidia-smi")
    if not executable:
        return None
    result = run_command(
        [
            executable,
            "--query-gpu=name,memory.total,memory.used,utilization.gpu",
            "--format=csv,noheader,nounits",
        ],
        ".",
        timeout_seconds=5,
        output_cap_chars=4000,
    )
    if result.exit_code != 0:
        return None
    rows: list[str] = []
    for line in result.stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != 4:
            continue
        name, total, used, util = parts
        rows.append(
            f"{name}: {used}/{total} MiB used, {util}% GPU"
        )
    return "; ".join(rows) if rows else result.stdout.strip() or None


def detect_hardware() -> HardwareInfo:
    return HardwareInfo(
        system=platform.system(),
        machine=platform.machine(),
        cpu_count=os.cpu_count() or 1,
        ram_bytes=_ram_bytes(),
        gpu_summary=_gpu_summary(),
    )
