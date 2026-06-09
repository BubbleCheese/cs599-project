"""
Douban MCP Server - Movie metadata provider.

MCP Protocol: Each tool is a function with typed signature.
When real API is unavailable, falls back to local movie database.

API Configuration:
- Uses direct HTML scraping from movie.douban.com
- No API key required

Tools:
    douban.search  - Search movies by title/genre/rating
    douban.detail  - Get detailed movie info by ID
"""
from __future__ import annotations

import json
import re
from typing import Optional, List

from src.models.schemas import Movie
from src.data.movies import search_movies, get_movie_by_id, MOVIE_DATABASE


# ===== MCP Tool Functions =====

def search(
    title: Optional[str] = None,
    genre: Optional[str] = None,
    rating_min: Optional[float] = None,
    max_duration: Optional[int] = None,
    limit: int = 10,
) -> str:
    """
    MCP Tool: douban.search
    Search movies from Douban database.
    
    Args:
        title: Movie title keyword (optional)
        genre: Genre filter, e.g. "科幻", "喜剧" (optional)
        rating_min: Minimum rating 0-10 (optional)
        max_duration: Maximum duration in minutes (optional)
        limit: Max results (default 10)
    
    Returns:
        JSON string: List[MovieMeta]
    """
    genres = [genre] if genre else None
    min_rating = rating_min or 0.0
    max_dur = max_duration or 999

    # Try real Douban search first
    try:
        return _search_douban(title, genres, min_rating, max_dur, limit)
    except Exception as e:
        print(f"  [Douban API] Search failed: {e}, falling back to local")
        pass  # Fall through to local

    # Fallback: local movie database
    results = search_movies(
        genres=genres,
        max_duration=max_dur,
        min_rating=min_rating,
        limit=limit,
    )

    if title:
        results = [m for m in results if title.lower() in m.title.lower()]

    return json.dumps(
        [{"id": m.movie_id, "title": m.title, "genres": m.genres,
          "duration": m.duration, "rating": m.rating, "year": m.year}
         for m in results],
        ensure_ascii=False
    )


def get_detail(movie_id: str) -> str:
    """
    MCP Tool: douban.detail
    Get detailed movie information by ID.
    
    Args:
        movie_id: Movie unique ID (e.g. "sf01", "co01", or Douban ID like "1292052")
    
    Returns:
        JSON string: MovieDetail or error
    """
    # Try real API first (if movie_id looks like a Douban ID)
    if movie_id.isdigit():
        try:
            return _detail_douban(movie_id)
        except Exception as e:
            print(f"  [Douban API] Detail failed: {e}, falling back to local")
            pass

    # Fallback: local database
    movie = get_movie_by_id(movie_id)
    if movie:
        return json.dumps({
            "id": movie.movie_id,
            "title": movie.title,
            "genres": movie.genres,
            "duration": movie.duration,
            "rating": movie.rating,
            "year": movie.year,
            "description": movie.description,
        }, ensure_ascii=False)

    return json.dumps({"error": "E3102", "message": f"影片不存在: {movie_id}"})


# ===== Douban HTML Scraping =====

def _search_douban(
    title: Optional[str],
    genres: Optional[List[str]],
    rating_min: float,
    max_duration: int,
    limit: int,
) -> str:
    """Scrape Douban movie search results."""
    import requests
    import json
    import re
    
    if not title:
        title = ""
    
    url = f"https://movie.douban.com/search?q={title}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    
    # Extract JSON data from window.__DATA__
    match = re.search(r'window\.__DATA__\s*=\s*(\{.*?\});', resp.text, re.DOTALL)
    if not match:
        return json.dumps([])
    
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return json.dumps([])
    
    results = []
    items = data.get("items", [])[:limit]
    
    for item in items:
        try:
            # Extract basic info
            movie_title = item.get("title", "") or item.get("name", "")
            movie_id = str(item.get("id", ""))
            
            # Parse abstract (e.g., "美国 / 英国 / 加拿大 / 剧情 / 科幻 / 冒险 / 星际穿越(港) / 星际效应(台) / 169分钟")
            abstract = item.get("abstract", "")
            
            # Extract year
            year_match = re.search(r"(\d{4})", abstract)
            year = int(year_match.group(1)) if year_match else 0
            
            # Extract duration
            duration_match = re.search(r"(\d+)\s*分钟", abstract)
            duration = int(duration_match.group(1)) if duration_match else 0
            
            # Extract genres
            genre_list = []
            # Look for genre keywords in abstract
            genre_keywords = ["剧情", "喜剧", "动作", "爱情", "科幻", "悬疑", "惊悚", "恐怖", 
                             "动画", "奇幻", "冒险", "战争", "历史", "纪录片", "音乐", "传记", "犯罪"]
            for keyword in genre_keywords:
                if keyword in abstract:
                    genre_list.append(keyword)
            
            # Get rating
            rating = item.get("rating", 0)
            if isinstance(rating, dict):
                rating = float(rating.get("value", 0))
            elif isinstance(rating, str):
                try:
                    rating = float(rating)
                except ValueError:
                    rating = 0.0
            else:
                try:
                    rating = float(rating)
                except (ValueError, TypeError):
                    rating = 0.0
            
            # Filter by criteria
            if rating < rating_min:
                continue
            if duration > max_duration and duration > 0:
                continue
            if genres and not any(g in genre_list for g in genres):
                continue
            
            results.append({
                "id": movie_id,
                "title": movie_title,
                "genres": genre_list,
                "duration": duration,
                "rating": rating,
                "year": year,
                "cover": item.get("cover_url", ""),
            })
        except Exception:
            continue
    
    return json.dumps(results, ensure_ascii=False)


def _detail_douban(movie_id: str) -> str:
    """Scrape detailed movie information from Douban."""
    import requests
    from bs4 import BeautifulSoup
    
    url = f"https://movie.douban.com/subject/{movie_id}/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    
    soup = BeautifulSoup(resp.text, "html.parser")
    
    # Extract title
    title_elem = soup.find("h1", class_="title")
    title = title_elem.get_text(strip=True).split("(")[0].strip() if title_elem else ""
    
    # Extract rating
    rating_elem = soup.find("strong", class_="ll rating_num")
    rating = float(rating_elem.get_text(strip=True)) if rating_elem else 0.0
    
    # Extract year
    year_elem = soup.find("span", class_="year")
    year_match = re.search(r"(\d{4})", year_elem.get_text(strip=True)) if year_elem else None
    year = int(year_match.group(1)) if year_match else 0
    
    # Extract info from infobox
    info_text = ""
    info_elem = soup.find("div", id="info")
    if info_elem:
        info_text = info_elem.get_text(separator="|", strip=True)
    
    # Extract duration
    duration_match = re.search(r"(\d+)\s*分钟", info_text)
    duration = int(duration_match.group(1)) if duration_match else 0
    
    # Extract genres
    genre_list = []
    genre_elems = soup.find_all("span", property="v:genre")
    if genre_elems:
        genre_list = [g.get_text(strip=True) for g in genre_elems]
    
    # Extract director
    director_elem = soup.find("a", rel="v:directedBy")
    director = director_elem.get_text(strip=True) if director_elem else ""
    
    # Extract actors
    actor_elems = soup.find_all("a", rel="v:starring")[:5]
    actors = [a.get_text(strip=True) for a in actor_elems]
    
    # Extract description
    desc_elem = soup.find("span", property="v:summary")
    description = desc_elem.get_text(strip=True) if desc_elem else ""
    
    # Extract cover
    cover_elem = soup.find("img", rel="v:image")
    cover = cover_elem["src"] if cover_elem else ""
    
    return json.dumps({
        "id": movie_id,
        "title": title,
        "genres": genre_list,
        "duration": duration,
        "rating": rating,
        "year": year,
        "description": description,
        "cover": cover,
        "director": director,
        "actors": actors,
    }, ensure_ascii=False)


# ===== MCP Server Registration =====

MCP_TOOLS = {
    "douban.search": {
        "function": search,
        "description": "Search movies by title, genre, rating, duration",
        "parameters": {
            "title": {"type": "string", "description": "Movie title keyword"},
            "genre": {"type": "string", "description": "Genre e.g. 科幻, 喜剧"},
            "rating_min": {"type": "number", "description": "Minimum rating 0-10"},
            "max_duration": {"type": "integer", "description": "Max duration in minutes"},
            "limit": {"type": "integer", "description": "Max results"},
        }
    },
    "douban.detail": {
        "function": get_detail,
        "description": "Get movie details by ID",
        "parameters": {
            "movie_id": {"type": "string", "description": "Movie unique ID"},
        }
    },
}


def call_tool(tool_name: str, **kwargs) -> str:
    """
    Unified tool calling interface.
    Used by MediatorAgent to invoke MCP tools.
    """
    if tool_name not in MCP_TOOLS:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    tool = MCP_TOOLS[tool_name]
    try:
        result = tool["function"](**kwargs)
        return result
    except Exception as e:
        return json.dumps({"error": f"Tool execution failed: {e}"})


def list_tools() -> List[dict]:
    """List all available MCP tools."""
    return [
        {
            "name": name,
            "description": info["description"],
            "parameters": info["parameters"],
        }
        for name, info in MCP_TOOLS.items()
    ]
