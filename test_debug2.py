import re

msg = '客户关系管理系统有哪些访问关系'
know_pat = r'(如何|怎么|流程|权限|提单|申请|审批|管理)'

match = re.search(know_pat, msg)
print(f'Message: {msg}')
print(f'Pattern: {know_pat}')
print(f'Match: {match}')
if match:
    print(f'Matched text: {match.group()}')
    print(f'Position: {match.span()}')
