import re

test_cases = [
    ('客户关系管理系统有哪些访问关系', True, 'Chinese system name with 管理'),
    ('办公自动化系统有哪些访问关系', True, 'Chinese system name'),
    ('N-CRM有哪些访问关系', True, 'System code'),
    ('访问关系如何管理', False, '管理 in knowledge context'),
    ('访问关系管理流程', False, '管理 in knowledge context'),
    ('如何申请访问关系', False, 'Knowledge query'),
]

# New patterns
sys_pat = r"(N-[A-Z]+|P-[A-Z-]+|[A-Z]+JS_[A-Z]+|[\u4e00-\u9fa5]+系统|部署单元)"
rel_pat = r"(有哪些访问关系|哪些系统访问|被.*访问|访问.*系统|之间.*访问关系)"
know_pat = r"(如何|怎么|流程|权限|提单|申请|审批)(?!系统)|(?<!关系)管理(?!系统)"

print("Testing new patterns:")
print("=" * 80)

for msg, expected, description in test_cases:
    has_sys = bool(re.search(sys_pat, msg))
    asks_rel = bool(re.search(rel_pat, msg))
    asks_know = bool(re.search(know_pat, msg))
    result = has_sys and asks_rel and not asks_know
    
    status = "✓" if result == expected else "✗"
    print(f"{status} {description}")
    print(f"  Message: {msg}")
    print(f"  has_sys={has_sys}, asks_rel={asks_rel}, asks_know={asks_know}")
    print(f"  Result: {result}, Expected: {expected}")
    print()
