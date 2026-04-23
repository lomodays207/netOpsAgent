"""
Input validation helpers used by rule-based parsing and routing.
"""
import re
from typing import Optional, Tuple


IP_CANDIDATE_RE = re.compile(r"\b(?:\d{1,3}\.){1,3}\d{0,3}\b")
PORT_RE = re.compile(r"(?:端口|port\s*|:)(\d{1,5})", re.IGNORECASE)

# Capture source/target pairs from common diagnosis phrasings.
PAIR_PATTERNS = (
    re.compile(
        r"(?P<source>[^\s,，。;；:：()（）]+?)到"
        r"(?P<target>[^\s,，。;；:：()（）]+?)"
        r"(?=的|端口|port\b|服务|service\b|连不通|不通|连不上|连接失败|访问失败|访问不了|超时|"
        r"timeout|refused|失败|故障|异常|$)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?P<source>[^\s,，。;；:：()（）]+?)访问"
        r"(?P<target>[^\s,，。;；:：()（）]+?)"
        r"(?=的|端口|port\b|服务|service\b|连不通|不通|连接失败|访问失败|访问不了|超时|"
        r"timeout|refused|失败|故障|异常|$)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?P<source>[^\s,，。;；:：()（）]+?)(?:连接|连)"
        r"(?P<target>[^\s,，。;；:：()（）]+?)"
        r"(?=的|端口|port\b|服务|service\b|连不通|不上|不通|超时|timeout|refused|失败|故障|异常|$)",
        re.IGNORECASE,
    ),
    re.compile(
        r"from\s+(?P<source>[A-Za-z0-9_.-]+)\s+to\s+(?P<target>[A-Za-z0-9_.-]+)",
        re.IGNORECASE,
    ),
)


def is_valid_ip(ip: str) -> bool:
    """Return True when the string is a valid IPv4 address."""
    if not ip or not isinstance(ip, str):
        return False

    match = re.match(r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$", ip.strip())
    if not match:
        return False

    return all(0 <= int(part) <= 255 for part in match.groups())


def looks_like_ip(value: str) -> bool:
    """Return True for dot-separated numeric tokens, even if invalid."""
    if not value or not isinstance(value, str):
        return False

    candidate = value.strip()
    return bool(re.match(r"^\d+(?:\.\d+){1,3}$", candidate))


def is_valid_port(port: int) -> bool:
    """Return True when the port is in the valid TCP/UDP range."""
    if port is None:
        return True
    return isinstance(port, int) and 1 <= port <= 65535


def _normalize_endpoint(value: str) -> str:
    return value.strip().strip(",，。;；:：()（）")


def extract_endpoint_pair(user_input: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract source and target endpoints without enforcing that they are IPs.
    """
    if not user_input or not user_input.strip():
        return None, None

    text = user_input.strip()
    for pattern in PAIR_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue

        source = _normalize_endpoint(match.group("source"))
        target = _normalize_endpoint(match.group("target"))
        if source and target:
            return source, target

    ip_candidates = IP_CANDIDATE_RE.findall(text)
    if len(ip_candidates) >= 2:
        return ip_candidates[0], ip_candidates[1]

    return None, None


def extract_network_info(user_input: str) -> Tuple[Optional[str], Optional[str], Optional[int], str]:
    """
    Extract source endpoint, target endpoint, and port from user input.

    Endpoints may be IPs, hostnames, or system names. IP-like values are still
    validated so malformed addresses can be rejected with a clear error.
    """
    source, target = extract_endpoint_pair(user_input)
    if not source or not target:
        return (
            None,
            None,
            None,
            "无法识别源和目标端点。请提供类似“源主机到目标主机端口80不通”的描述。",
        )

    if looks_like_ip(source) and not is_valid_ip(source):
        return (
            None,
            None,
            None,
            f"源IP地址格式不正确: {source}。正确格式应为 x.x.x.x，例如 192.168.1.1。",
        )

    if looks_like_ip(target) and not is_valid_ip(target):
        return (
            None,
            None,
            None,
            f"目标IP地址格式不正确: {target}。正确格式应为 x.x.x.x，例如 192.168.1.1。",
        )

    port = None
    match = PORT_RE.search(user_input)
    if match:
        port = int(match.group(1))
    else:
        # Support common "10.0.0.1:80" style phrasing.
        colon_ports = re.findall(r":(\d{1,5})\b", user_input)
        if colon_ports:
            port = int(colon_ports[-1])

    if port is not None and not is_valid_port(port):
        return (
            None,
            None,
            None,
            f"端口号超出有效范围: {port}。端口号应在 1-65535 之间。",
        )

    return source, target, port, ""
