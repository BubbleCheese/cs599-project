import sys
sys.path.insert(0, '.')

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
    print(f"Total items: {len(data['items'])}")
    
    for idx, item in enumerate(data['items']):
        title = item.get('title', '')
        movie_id = str(item.get('id', ''))
        abstract = item.get('abstract', '')
        rating_val = item.get('rating')
        
        # Debug rating
        print(f"\n=== Item {idx + 1} ===")
        print(f"ID: {movie_id}")
        print(f"Title type: {type(title)}")
        print(f"Rating type: {type(rating_val)}")
        print(f"Rating repr: {repr(rating_val)}")
        
        # Try to extract rating
        if isinstance(rating_val, dict):
            rating_val = rating_val.get('value', 0)
        elif isinstance(rating_val, str):
            try:
                rating_val = float(rating_val)
            except ValueError:
                rating_val = 0.0
        else:
            try:
                rating_val = float(rating_val)
            except (ValueError, TypeError):
                rating_val = 0.0
        
        print(f"Processed rating: {rating_val}")
        print(f"Abstract: {abstract}")
        
        # Check year extraction
        import re
        year_match = re.search(r"(\d{4})", abstract)
        year = int(year_match.group(1)) if year_match else 0
        print(f"Year: {year}")
        
        # Check duration extraction
        duration_match = re.search(r"(\d+)\s*分钟", abstract)
        duration = int(duration_match.group(1)) if duration_match else 0
        print(f"Duration: {duration}")
        
        # Check genre extraction
        genre_keywords = ["剧情", "喜剧", "动作", "爱情", "科幻", "悬疑", "惊悚", "恐怖", 
                         "动画", "奇幻", "冒险", "战争", "历史", "纪录片", "音乐", "传记", "犯罪"]
        genre_list = []
        for keyword in genre_keywords:
            if keyword in abstract:
                genre_list.append(keyword)
        print(f"Genres: {genre_list}")
        
        # Check filtering
        rating_min = 0.0
        max_dur = 999
        genres = None
        
        if rating_val < rating_min:
            print("Filtered by rating")
        elif duration > max_dur and duration > 0:
            print("Filtered by duration")
        elif genres and not any(g in genre_list for g in genres):
            print("Filtered by genre")
        else:
            print("PASSED filtering")
