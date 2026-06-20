import requests
import re
import json
import sys

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

resp = requests.get("https://movie.douban.com/search?q=星际穿越", headers=headers, timeout=15)
match = re.search(r'window\.__DATA__\s*=\s*(\{.*?\});', resp.text, re.DOTALL)

if match:
    data = json.loads(match.group(1))
    for idx, item in enumerate(data['items'][:3]):
        print(f"=== Item {idx + 1} ===")
        # Print title safely
        title = item.get('title', '')
        if isinstance(title, str):
            title = title.encode('utf-8', errors='replace').decode('utf-8')
        print(f"Title: {title}")
        print(f"ID: {item.get('id', '')}")
        rating = item.get('rating')
        print(f"Rating type: {type(rating)}")
        print(f"Rating value: {rating}")
        if isinstance(rating, dict):
            print(f"Rating keys: {list(rating.keys())}")
        print(f"Abstract: {item.get('abstract', '')[:50]}")
        print("-" * 50)
