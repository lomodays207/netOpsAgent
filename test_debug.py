import re

msg = '客户关系管理系统有哪些访问关系'

sys_pat = r'(N-[A-Z]+|P-[A-Z-]+|[A-Z]+JS_[A-Z]+|客户关系管理系统|办公自动化系统|部署单元)'
rel_pat = r'(有哪些访问关系|哪些系统访问|被.*访问|访问.*系统|之间.*访问关系)'
know_pat = r'(如何|怎么|流程|权限|提单|申请|审批|管理)'

has_sys = bool(re.search(sys_pat, msg))
asks_rel = bool(re.search(rel_pat, msg))
asks_know = bool(re.search(know_pat, msg))

print(f'Message: {msg}')
print(f'has_system_identifier: {has_sys}')
print(f'asks_for_relations: {asks_rel}')
print(f'asks_for_knowledge: {asks_know}')
print(f'Result: {has_sys and asks_rel and not asks_know}')
