import requests
import re
import json

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

resp = requests.get("https://movie.douban.com/search?q=星际穿越", headers=headers, timeout=15)
print(f"Status: {resp.status_code}")

# Check if window.__DATA__ exists
pos = resp.text.find('window.__DATA__')
print(f"Found window.__DATA__ at position: {pos}")

if pos != -1:
    # Extract the JSON
    snippet = resp.text[pos:pos+200]
    print(f"Context: {snippet}")
    
    # Try to find the full JSON
    match = re.search(r'window\.__DATA__\s*=\s*(\{.*?\});', resp.text, re.DOTALL)
    if match:
        print(f"Match found, length: {len(match.group(1))}")
        try:
            data = json.loads(match.group(1))
            print(f"JSON parsed successfully")
            print(f"Keys: {list(data.keys())}")
            if 'items' in data:
                print(f"Items count: {len(data['items'])}")
                if data['items']:
                    print(f"First item: {json.dumps(data['items'][0], ensure_ascii=False)[:500]}")
        except Exception as e:
            print(f"JSON parse error: {e}")
    else:
        print("No match found")
