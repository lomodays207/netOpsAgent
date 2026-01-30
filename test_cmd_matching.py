"""
快速验证脚本 - 测试命令匹配功能
"""
import sys
import os

# 添加src到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# 测试命令匹配逻辑
def test_command_matching():
    print("=" * 60)
    print("测试命令匹配逻辑")
    print("=" * 60)
    
    test_commands = [
        "ss -tuln | grep ':80'",
        "ss -tunlp | grep ':80'",
        "ss -tlnp | grep ':80'",
        "netstat -tunlp | grep ':80'",
        "ping -c 4 -W 5 10.0.2.20",
        "timeout 5 bash -c '</dev/tcp/10.0.2.20/80'",
        "iptables -L INPUT -n -v",
        "traceroute -m 30 -w 3 10.0.2.20",
        "ip route show",
    ]
    
    # 模拟 _match_command_key 逻辑
    for cmd in test_commands:
        normalized_cmd = ' '.join(cmd.lower().split())
        
        if "telnet" in normalized_cmd or "/dev/tcp" in normalized_cmd:
            key = "telnet_test"
        elif "ss" in normalized_cmd and ("tuln" in normalized_cmd or "tunlp" in normalized_cmd or "tlnp" in normalized_cmd):
            key = "ss_listen"
        elif "netstat" in normalized_cmd and ("tunlp" in normalized_cmd or "tlnp" in normalized_cmd):
            key = "ss_listen"
        elif "ping" in normalized_cmd and "-c" in normalized_cmd:
            key = "ping"
        elif "iptables" in normalized_cmd and ("-l" in normalized_cmd or "list" in normalized_cmd):
            key = "iptables_list"
        elif "traceroute" in normalized_cmd:
            key = "traceroute"
        else:
            key = "unknown_command"
        
        status = "✓" if key != "unknown_command" else "⚠"
        print(f"{status} {cmd[:40]:40s} -> {key}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    test_command_matching()
