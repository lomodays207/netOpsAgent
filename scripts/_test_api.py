import urllib.request
import json

# Test 1: query access assets list
print("Testing /api/v1/assets/access-relations...")
url = "http://localhost:8000/api/v1/assets/access-relations"
with urllib.request.urlopen(url) as res:
    data = json.loads(res.read())
    print(f"  Status: {data.get('status')}")
    print(f"  Total records: {data.get('total')}")
    items = data.get("items", [])
    if items:
        first = items[0]
        print(f"  First: {first.get('src_system')} -> {first.get('dst_system')} ({first.get('protocol')}:{first.get('port')})")

# Test 2: chat query
print()
print("Testing chat-query API with keyword=N-AQM...")
url2 = "http://localhost:8000/api/v1/assets/access-relations/chat-query?keyword=N-AQM"
with urllib.request.urlopen(url2) as res:
    data2 = json.loads(res.read())
    print(f"  Total: {data2.get('total')}")
    markdown = data2.get("markdown", "")
    lines = markdown.split("\n")
    for line in lines[:6]:
        print(f"  {line[:100]}")

print()
print("All tests passed!")
