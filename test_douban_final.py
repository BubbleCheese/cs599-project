import sys
sys.path.insert(0, '.')

from src.tools.douban_mcp import search

print("Testing search...")
result = search(title='星际穿越')
print(f"Result type: {type(result)}")
print(f"Result length: {len(result)}")

# Write to file to avoid console encoding issues
with open('douban_result.json', 'w', encoding='utf-8') as f:
    f.write(result)
print("Result saved to douban_result.json")

# Read and print safely
with open('douban_result.json', 'r', encoding='utf-8') as f:
    content = f.read()
    print(f"\nContent preview (first 500 chars):")
    print(content[:500])