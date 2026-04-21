#!/usr/bin/env python3
"""
测试"办公自动化有哪些访问关系"查询是否正确跳过 RAG
"""
from src.api import is_access_relation_data_query

# 测试各种查询
test_cases = [
    ("办公自动化有哪些访问关系", True, "数据查询 - 应跳过 RAG"),
    ("办公自动化系统有哪些访问关系", True, "数据查询 - 应跳过 RAG"),
    ("客户关系管理有哪些访问关系", True, "数据查询 - 应跳过 RAG"),
    ("客户关系管理系统有哪些访问关系", True, "数据查询 - 应跳过 RAG"),
    ("N-CRM有哪些访问关系", True, "数据查询 - 应跳过 RAG"),
    ("CRMJS_AP部署单元有哪些访问关系", True, "数据查询 - 应跳过 RAG"),
    ("办公自动化如何申请权限", False, "知识查询 - 应使用 RAG"),
    ("访问关系如何开权限", False, "知识查询 - 应使用 RAG"),
    ("如何排查网络故障", False, "一般问题 - 应使用 RAG"),
]

print("=" * 80)
print("测试访问关系数据查询检测功能")
print("=" * 80)
print()

all_passed = True
for query, expected, description in test_cases:
    result = is_access_relation_data_query(query)
    status = "✅ PASS" if result == expected else "❌ FAIL"
    
    if result != expected:
        all_passed = False
    
    print(f"{status} | {description}")
    print(f"     查询: {query}")
    print(f"     预期: {expected}, 实际: {result}")
    print()

print("=" * 80)
if all_passed:
    print("✅ 所有测试通过！")
    print()
    print("现在当用户提问'办公自动化有哪些访问关系'时：")
    print("1. 系统会检测到这是访问关系数据查询")
    print("2. 跳过 RAG 知识库检索")
    print("3. 发出 rag_skipped 事件")
    print("4. LLM 直接调用 query_access_relations 工具查询实时数据")
else:
    print("❌ 部分测试失败，请检查！")
print("=" * 80)
