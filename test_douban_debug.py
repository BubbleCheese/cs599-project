import sys
sys.path.insert(0, '.')

from src.tools.douban_mcp import _search_douban

# Test with debug output
print("Testing search...")
result = _search_douban("星际穿越", None, 0.0, 999, 5)
print(f"Result: {result}")

# Let's also check what's happening inside
import requests
import re
import json

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

resp = requests.get("https://movie.douban.com/search?q=星际穿越", headers=headers, timeout=15)
match = re.search(r'window\.__DATA__\s*=\s*(\{.*?\});', resp.text, re.DOTALL)

if match:
    data = json.loads(match.group(1))
    print(f"\nTotal items: {len(data['items'])}")
    for item in data['items']:
        title = item.get('title', '')
        rating_val = item.get('rating')
        if isinstance(rating_val, dict):
            rating_val = rating_val.get('value', 0)
        print(f"Title: {title[:20]}... | Rating: {rating_val}")
