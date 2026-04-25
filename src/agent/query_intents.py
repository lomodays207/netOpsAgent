"""Shared intent detectors for structured general-chat queries."""

from __future__ import annotations

import re
from typing import Optional


HOST_IP_RE = re.compile(r"(?<![A-Za-z0-9.])(?:\d{1,3}\.){3}\d{1,3}(?![A-Za-z0-9.])")
PORT_NUMBER_RE = re.compile(r"(?<![A-Za-z0-9.])(\d{1,5})(?![A-Za-z0-9.])")
HOST_PORT_STATUS_RE = re.compile(
    r"(监听|正常|存活|服务端口|端口状态|alive|listen|listening|status)",
    re.IGNORECASE,
)
HOW_TO_RE = re.compile(
    r"(如何|怎么|怎样|步骤|方法|流程|排查|指南|原理|思路)",
    re.IGNORECASE,
)


def detect_host_port_status_query(message: str) -> Optional[dict[str, int | str]]:
    """Detect direct questions about whether a port is alive on a single host."""

    text = (message or "").strip()
    if not text:
        return None

    if HOW_TO_RE.search(text):
        return None

    if not HOST_PORT_STATUS_RE.search(text):
        return None

    ip_addresses = HOST_IP_RE.findall(text)
    if len(ip_addresses) != 1:
        return None

    ports = {
        int(raw_port)
        for raw_port in PORT_NUMBER_RE.findall(text)
        if 1 <= int(raw_port) <= 65535
    }
    if len(ports) != 1:
        return None

    return {
        "host": ip_addresses[0],
        "port": next(iter(ports)),
    }
