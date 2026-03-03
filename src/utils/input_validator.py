"""
输入验证工具函数

用于验证用户输入的网络参数格式
"""
import re
from typing import Tuple, Optional


def is_valid_ip(ip: str) -> bool:
    """
    验证IP地址格式是否正确
    
    Args:
        ip: IP地址字符串
        
    Returns:
        bool: IP格式是否合法
        
    示例:
        >>> is_valid_ip("10.0.1.10")
        True
        >>> is_valid_ip("10.1.10")
        False
        >>> is_valid_ip("256.0.0.1")
        False
    """
    if not ip or not isinstance(ip, str):
        return False
    
    # IP地址格式: x.x.x.x,每个x为0-255
    pattern = r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$'
    match = re.match(pattern, ip.strip())
    
    if not match:
        return False
    
    # 检查每个段是否在0-255范围内
    for group in match.groups():
        if int(group) > 255:
            return False
    
    return True


def is_valid_port(port: int) -> bool:
    """
    验证端口号是否在有效范围内
    
    Args:
        port: 端口号
        
    Returns:
        bool: 端口号是否有效 (1-65535)
    """
    if port is None:
        return True  # 端口号是可选的
    
    return isinstance(port, int) and 1 <= port <= 65535


def extract_network_info(user_input: str) -> Tuple[Optional[str], Optional[str], Optional[int], str]:
    """
    从用户输入中提取网络信息并验证
    
    Args:
        user_input: 用户输入的自然语言描述
        
    Returns:
        tuple: (源IP, 目标IP, 端口, 错误消息)
               如果验证通过,错误消息为空字符串
               如果验证失败,返回的IP/端口为None,错误消息描述问题
    
    示例:
        >>> extract_network_info("10.0.1.10到10.0.2.20端口80不通")
        ('10.0.1.10', '10.0.2.20', 80, '')
        
        >>> extract_network_info("10.1.10到10.0.2.20端口80不通")
        (None, None, None, '源IP地址格式不正确: 10.1.10。正确格式应为: x.x.x.x (如: 192.168.1.1)')
    """
    # 提取主机名/IP（简化版）
    parts = user_input.replace("到", " ").replace("端口", " ").replace("不通", "").strip().split()
    
    if len(parts) < 2:
        return None, None, None, "无法识别源IP和目标IP。请使用格式: '源IP到目标IP端口XX不通' (例如: 10.0.1.10到10.0.2.20端口80不通)"
    
    source = parts[0].strip()
    target = parts[1].strip()
    
    # 验证源IP
    if not is_valid_ip(source):
        return None, None, None, f"源IP地址格式不正确: {source}。正确格式应为: x.x.x.x (如: 192.168.1.1)"
    
    # 验证目标IP
    if not is_valid_ip(target):
        return None, None, None, f"目标IP地址格式不正确: {target}。正确格式应为: x.x.x.x (如: 192.168.1.1)"
    
    # 提取端口号
    port = None
    for part in parts:
        if part.isdigit():
            port = int(part)
            break
    
    # 验证端口号
    if port is not None and not is_valid_port(port):
        return None, None, None, f"端口号超出有效范围: {port}。端口号应在 1-65535 之间"
    
    return source, target, port, ""


if __name__ == "__main__":
    # 测试用例
    test_cases = [
        "10.0.1.10到10.0.2.20端口80不通",  # 正确
        "10.1.10到10.0.2.20端口80不通",  # 错误: 源IP不完整
        "10.0.1.10到10.0.2端口80不通",  # 错误: 目标IP不完整
        "256.0.0.1到10.0.2.20端口80不通",  # 错误: 源IP超范围
        "10.0.1.10到10.0.2.20端口99999不通",  # 错误: 端口超范围
    ]
    
    print("=== IP验证测试 ===")
    for test in test_cases:
        source, target, port, error = extract_network_info(test)
        print(f"\n输入: {test}")
        if error:
            print(f"  ❌ {error}")
        else:
            print(f"  ✅ 源IP: {source}, 目标IP: {target}, 端口: {port}")
