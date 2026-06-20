import requests
import re
import json

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

resp = requests.get("https://movie.douban.com/search?q=星际穿越", headers=headers, timeout=15)
match = re.search(r'window\.__DATA__\s*=\s*(\{.*?\});', resp.text, re.DOTALL)

if match:
    data = json.loads(match.group(1))
    for item in data['items'][:3]:
        print(f"Title: {item.get('title', '')}")
        print(f"ID: {item.get('id', '')}")
        print(f"Rating: {item.get('rating', 'N/A')}")
        print(f"Abstract: {item.get('abstract', '')}")
        print("-" * 50)
