"""
单元测试：测试 query_access_relations 工具函数的 IP 地址参数
"""
import asyncio
from src.session_manager import get_session_manager


async def test_tool_function():
    """测试工具函数直接调用"""
    
    # 初始化
    session_manager = get_session_manager()
    await session_manager.initialize()
    
    print("\n" + "="*60)
    print("测试 query_access_relations 工具函数的 IP 地址参数")
    print("="*60)
    
    # 测试 1: 通过 src_ip 查询
    print("\n【测试 1】通过 src_ip 查询")
    result = await session_manager.db.query_access_relations(
        src_ip="10.40.1.10",
        direction="outbound"
    )
    print(f"查询参数: src_ip='10.40.1.10', direction='outbound'")
    print(f"结果: 找到 {result['total']} 条记录")
    if result['items']:
        for item in result['items']:
            print(f"  - {item['src_system']} ({item['src_ip']}) -> {item['dst_system']} ({item['dst_ip']}) 端口:{item['port']}")
    
    # 测试 2: 通过 dst_ip 查询
    print("\n【测试 2】通过 dst_ip 查询")
    result = await session_manager.db.query_access_relations(
        dst_ip="10.38.1.100",
        direction="inbound"
    )
    print(f"查询参数: dst_ip='10.38.1.100', direction='inbound'")
    print(f"结果: 找到 {result['total']} 条记录")
    if result['items']:
        for item in result['items']:
            print(f"  - {item['src_system']} ({item['src_ip']}) -> {item['dst_system']} ({item['dst_ip']}) 端口:{item['port']}")
    
    # 测试 3: 同时指定 src_ip 和 dst_ip
    print("\n【测试 3】同时指定 src_ip 和 dst_ip")
    result = await session_manager.db.query_access_relations(
        src_ip="10.40.1.10",
        dst_ip="10.38.1.100",
        direction="outbound"
    )
    print(f"查询参数: src_ip='10.40.1.10', dst_ip='10.38.1.100', direction='outbound'")
    print(f"结果: 找到 {result['total']} 条记录")
    if result['items']:
        for item in result['items']:
            print(f"  - {item['src_system']} ({item['src_ip']}) -> {item['dst_system']} ({item['dst_ip']}) 端口:{item['port']}")
    
    # 测试 4: 混合查询（系统编码 + IP）
    print("\n【测试 4】混合查询（系统编码 + dst_ip）")
    result = await session_manager.db.query_access_relations(
        system_code="N-OA",
        dst_ip="10.38.1.100",
        direction="outbound"
    )
    print(f"查询参数: system_code='N-OA', dst_ip='10.38.1.100', direction='outbound'")
    print(f"结果: 找到 {result['total']} 条记录")
    if result['items']:
        for item in result['items']:
            print(f"  - {item['src_system']} ({item['src_ip']}) -> {item['dst_system']} ({item['dst_ip']}) 端口:{item['port']}")
    
    # 测试 5: 验证工具参数定义
    print("\n【测试 5】验证 GeneralChatToolAgent 工具参数定义")
    from src.agent.general_chat_agent import QueryAccessRelationsInput
    from pydantic import ValidationError
    
    # 测试有效的输入
    try:
        valid_input = QueryAccessRelationsInput(
            src_ip="10.0.1.10",
            dst_ip="10.0.2.20",
            direction="outbound"
        )
        print(f"✓ 有效输入验证通过:")
        print(f"  src_ip: {valid_input.src_ip}")
        print(f"  dst_ip: {valid_input.dst_ip}")
        print(f"  direction: {valid_input.direction}")
    except ValidationError as e:
        print(f"✗ 验证失败: {e}")
    
    # 测试混合输入
    try:
        mixed_input = QueryAccessRelationsInput(
            system_code="N-CRM",
            src_ip="10.38.1.100",
            direction="both"
        )
        print(f"✓ 混合输入验证通过:")
        print(f"  system_code: {mixed_input.system_code}")
        print(f"  src_ip: {mixed_input.src_ip}")
        print(f"  direction: {mixed_input.direction}")
    except ValidationError as e:
        print(f"✗ 验证失败: {e}")
    
    print("\n" + "="*60)
    print("所有测试完成！")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(test_tool_function())
