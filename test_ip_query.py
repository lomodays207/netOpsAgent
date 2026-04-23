"""
测试 IP 地址查询访问关系功能
"""
import asyncio
from src.db.database import SessionDatabase


async def test_ip_query():
    """测试通过 IP 地址查询访问关系"""
    db = SessionDatabase()
    await db.initialize()
    
    # 测试 1: 通过源 IP 查询（使用数据库中实际存在的 IP）
    print("\n=== 测试 1: 通过源 IP 查询 ===")
    result = await db.query_access_relations(
        src_ip="10.38.1.100\n10.38.1.101",  # N-CRM 的源 IP
        direction="outbound"
    )
    print(f"查询 src_ip='10.38.1.100\\n10.38.1.101' 的访问关系:")
    print(f"  总数: {result['total']}")
    if result['items']:
        for item in result['items'][:3]:  # 只显示前3条
            src_ip_display = item['src_ip'].replace('\n', ', ') if item.get('src_ip') else 'N/A'
            dst_ip_display = item['dst_ip'].replace('\n', ', ') if item.get('dst_ip') else 'N/A'
            print(f"  - {item['src_system']} ({src_ip_display}) -> {item['dst_system']} ({dst_ip_display}) 端口:{item['port']}")
    else:
        print("  未找到记录")
    
    # 测试 2: 通过目标 IP 查询
    print("\n=== 测试 2: 通过目标 IP 查询 ===")
    result = await db.query_access_relations(
        dst_ip="10.38.1.100",  # N-CRM 的目标 IP
        direction="inbound"
    )
    print(f"查询 dst_ip='10.38.1.100' 的访问关系:")
    print(f"  总数: {result['total']}")
    if result['items']:
        for item in result['items'][:3]:
            src_ip_display = item['src_ip'].replace('\n', ', ') if item.get('src_ip') else 'N/A'
            dst_ip_display = item['dst_ip'].replace('\n', ', ') if item.get('dst_ip') else 'N/A'
            print(f"  - {item['src_system']} ({src_ip_display}) -> {item['dst_system']} ({dst_ip_display}) 端口:{item['port']}")
    else:
        print("  未找到记录")
    
    # 测试 3: 通过单个 IP 查询（部分匹配）
    print("\n=== 测试 3: 通过单个 IP 查询 ===")
    result = await db.query_access_relations(
        src_ip="10.40.1.10",  # N-OA 的源 IP
        direction="outbound"
    )
    print(f"查询 src_ip='10.40.1.10' 的访问关系:")
    print(f"  总数: {result['total']}")
    if result['items']:
        for item in result['items']:
            src_ip_display = item['src_ip'].replace('\n', ', ') if item.get('src_ip') else 'N/A'
            dst_ip_display = item['dst_ip'].replace('\n', ', ') if item.get('dst_ip') else 'N/A'
            print(f"  - {item['src_system']} ({src_ip_display}) -> {item['dst_system']} ({dst_ip_display}) 端口:{item['port']}")
    else:
        print("  未找到记录")
    
    # 测试 4: 查询所有访问关系（查看数据库中有哪些 IP）
    print("\n=== 测试 4: 查看数据库中的所有访问关系 ===")
    result = await db.query_access_relations(
        system_code="N-CRM",
        direction="both"
    )
    print(f"N-CRM 系统的访问关系:")
    print(f"  总数: {result['total']}")
    if result['items']:
        print("  所有记录:")
        for item in result['items']:
            src_ip_display = item['src_ip'].replace('\n', ', ') if item.get('src_ip') else 'N/A'
            dst_ip_display = item['dst_ip'].replace('\n', ', ') if item.get('dst_ip') else 'N/A'
            print(f"  - {item['src_system']} ({src_ip_display}) -> {item['dst_system']} ({dst_ip_display}) 端口:{item['port']}")
    else:
        print("  未找到记录")


if __name__ == "__main__":
    asyncio.run(test_ip_query())
