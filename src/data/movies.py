"""
Mock movie dataset for MVP (50 movies).
Covers major genres with varied durations and ratings.
"""
from typing import List
from src.models.schemas import Movie


MOVIE_DATABASE: List[Movie] = [
    # ===== Sci-Fi =====
    Movie(movie_id="sf01", title="星际穿越", genres=["科幻", "剧情"], duration=169, rating=9.3, year=2014,
          description="地球环境恶化，一组宇航员穿越虫洞寻找新家园"),
    Movie(movie_id="sf02", title="盗梦空间", genres=["科幻", "动作"], duration=148, rating=9.2, year=2010,
          description="造梦师潜入他人梦境窃取秘密"),
    Movie(movie_id="sf03", title="银翼杀手2049", genres=["科幻", "剧情"], duration=164, rating=8.0, year=2017,
          description="复制人杀手发现惊天秘密"),
    Movie(movie_id="sf04", title="头号玩家", genres=["科幻", "动作", "冒险"], duration=140, rating=8.6, year=2018,
          description="虚拟现实世界中的寻宝冒险"),
    Movie(movie_id="sf05", title="降临", genres=["科幻", "剧情"], duration=116, rating=7.8, year=2016,
          description="语言学家与外星人的首次接触"),
    Movie(movie_id="sf06", title="机械姬", genres=["科幻", "悬疑"], duration=108, rating=7.6, year=2014,
          description="程序员与人工智能的图灵测试"),
    Movie(movie_id="sf07", title="地心引力", genres=["科幻", "惊悚"], duration=91, rating=7.7, year=2013,
          description="宇航员在太空灾难中求生"),
    Movie(movie_id="sf08", title="她", genres=["科幻", "爱情", "剧情"], duration=126, rating=8.0, year=2013,
          description="男子与人工智能操作系统坠入爱河"),
    
    # ===== Comedy =====
    Movie(movie_id="co01", title="西虹市首富", genres=["喜剧"], duration=118, rating=6.5, year=2018,
          description="一个月内花光十亿的挑战"),
    Movie(movie_id="co02", title="夏洛特烦恼", genres=["喜剧", "剧情"], duration=104, rating=7.7, year=2015,
          description="中年男子梦回青春时代"),
    Movie(movie_id="co03", title="人在囧途", genres=["喜剧"], duration=91, rating=7.6, year=2010,
          description="春运回家路上的爆笑旅程"),
    Movie(movie_id="co04", title="疯狂的石头", genres=["喜剧", "犯罪"], duration=98, rating=8.5, year=2006,
          description="围绕一块翡翠展开的黑色幽默"),
    Movie(movie_id="co05", title="羞羞的铁拳", genres=["喜剧", "动作"], duration=100, rating=6.9, year=2017,
          description="拳击手与记者灵魂互换"),
    Movie(movie_id="co06", title="唐人街探案", genres=["喜剧", "悬疑"], duration=136, rating=7.5, year=2015,
          description="曼谷唐人街破案奇遇"),
    Movie(movie_id="co07", title="泰囧", genres=["喜剧", "冒险"], duration=105, rating=7.4, year=2012,
          description="三人泰国之旅的囧事连连"),
    
    # ===== Action =====
    Movie(movie_id="ac01", title="战狼2", genres=["动作", "战争"], duration=123, rating=7.1, year=2017,
          description="退役特种兵非洲营救同胞"),
    Movie(movie_id="ac02", title="红海行动", genres=["动作", "战争"], duration=138, rating=8.2, year=2018,
          description="中国海军海外撤侨行动"),
    Movie(movie_id="ac03", title="让子弹飞", genres=["动作", "剧情", "喜剧"], duration=132, rating=8.9, year=2010,
          description="县长与土匪的权力博弈"),
    Movie(movie_id="ac04", title="疾速追杀", genres=["动作", "犯罪"], duration=101, rating=7.3, year=2014,
          description="退休杀手为爱犬复仇"),
    Movie(movie_id="ac05", title="碟中谍6", genres=["动作", "冒险"], duration=147, rating=7.8, year=2018,
          description=" Ethan Hunt 执行不可能的任务"),
    Movie(movie_id="ac06", title="疯狂的麦克斯4", genres=["动作", "科幻"], duration=120, rating=8.1, year=2015,
          description="末日荒原上的公路追逐战"),
    
    # ===== Drama =====
    Movie(movie_id="dr01", title="肖申克的救赎", genres=["剧情", "犯罪"], duration=142, rating=9.7, year=1994,
          description="银行家冤狱中的希望与救赎"),
    Movie(movie_id="dr02", title="阿甘正传", genres=["剧情", "爱情"], duration=142, rating=9.5, year=1994,
          description="智商75男子的人生传奇"),
    Movie(movie_id="dr03", title="霸王别姬", genres=["剧情", "爱情"], duration=171, rating=9.6, year=1993,
          description="两位京剧演员半个世纪的悲欢离合"),
    Movie(movie_id="dr04", title="美丽人生", genres=["剧情", "喜剧", "战争"], duration=116, rating=9.5, year=1997,
          description="父亲用谎言保护儿子度过集中营"),
    Movie(movie_id="dr05", title="熔炉", genres=["剧情"], duration=125, rating=9.3, year=2011,
          description="揭露聋哑学校性侵丑闻"),
    Movie(movie_id="dr06", title="绿皮书", genres=["剧情", "喜剧", "传记"], duration=130, rating=8.9, year=2018,
          description="黑人钢琴家与白人司机的南方之旅"),
    Movie(movie_id="dr07", title="我不是药神", genres=["剧情", "喜剧"], duration=117, rating=9.0, year=2018,
          description="白血病患者与仿制药代购者的故事"),
    Movie(movie_id="dr08", title="海上钢琴师", genres=["剧情", "音乐"], duration=165, rating=9.3, year=1998,
          description="一生未下船的钢琴天才"),
    
    # ===== Romance =====
    Movie(movie_id="ro01", title="泰坦尼克号", genres=["爱情", "剧情"], duration=194, rating=9.4, year=1997,
          description="沉船上的跨越阶级之恋"),
    Movie(movie_id="ro02", title="怦然心动", genres=["爱情", "剧情", "喜剧"], duration=90, rating=9.1, year=2010,
          description="青梅竹马的双视角成长故事"),
    Movie(movie_id="ro03", title="恋恋笔记本", genres=["爱情", "剧情"], duration=123, rating=8.5, year=2004,
          description="养老院中老人讲述的爱情故事"),
    Movie(movie_id="ro04", title="你的名字", genres=["爱情", "动画", "奇幻"], duration=106, rating=8.4, year=2016,
          description="互换身体的少年少女跨越时空寻找彼此"),
    
    # ===== Animation =====
    Movie(movie_id="an01", title="千与千寻", genres=["动画", "奇幻", "冒险"], duration=125, rating=9.4, year=2001,
          description="少女在神灵世界的冒险与成长"),
    Movie(movie_id="an02", title="寻梦环游记", genres=["动画", "音乐", "奇幻"], duration=105, rating=9.1, year=2017,
          description="墨西哥亡灵节上的亲情之旅"),
    Movie(movie_id="an03", title="疯狂动物城", genres=["动画", "喜剧", "冒险"], duration=108, rating=9.2, year=2016,
          description="兔子警官与狐狸搭档破案"),
    Movie(movie_id="an04", title="哪吒之魔童降世", genres=["动画", "喜剧", "奇幻"], duration=110, rating=8.4, year=2019,
          description="逆天改命的魔童哪吒"),
    
    # ===== Thriller / Horror =====
    Movie(movie_id="th01", title="看不见的客人", genres=["悬疑", "惊悚", "犯罪"], duration=106, rating=8.8, year=2016,
          description="企业家密室杀人案反转不断"),
    Movie(movie_id="th02", title="恐怖游轮", genres=["悬疑", "惊悚", "恐怖"], duration=99, rating=8.5, year=2009,
          description="游轮上的无限循环死亡陷阱"),
    Movie(movie_id="th03", title="招魂", genres=["恐怖", "惊悚"], duration=112, rating=7.6, year=2013,
          description="超自然现象调查员对抗恶灵"),
    
    # ===== Fantasy / Adventure =====
    Movie(movie_id="fa01", title="指环王：护戒使者", genres=["奇幻", "冒险", "动作"], duration=178, rating=9.1, year=2001,
          description="霍比特人护送魔戒的史诗冒险"),
    Movie(movie_id="fa02", title="哈利波特与魔法石", genres=["奇幻", "冒险"], duration=152, rating=8.9, year=2001,
          description="少年巫师霍格沃茨的魔法之旅"),
    Movie(movie_id="fa03", title="阿凡达", genres=["科幻", "动作", "奇幻"], duration=162, rating=8.7, year=2009,
          description="外星潘多拉星球上的殖民与反抗"),
    
    # ===== Music / Biography =====
    Movie(movie_id="mu01", title="波西米亚狂想曲", genres=["音乐", "传记", "剧情"], duration=134, rating=8.6, year=2018,
          description="皇后乐队主唱 Freddie Mercury 的传奇人生"),
    Movie(movie_id="mu02", title="爱乐之城", genres=["音乐", "爱情", "剧情"], duration=128, rating=8.3, year=2016,
          description="洛杉矶追梦男女的爱情与梦想抉择"),
    
    # ===== Crime / Mystery =====
    Movie(movie_id="cr01", title="无间道", genres=["犯罪", "剧情", "惊悚"], duration=101, rating=9.3, year=2002,
          description="警方与黑帮互派卧底的经典对决"),
    Movie(movie_id="cr02", title="窃听风暴", genres=["悬疑", "剧情"], duration=137, rating=9.2, year=2006,
          description="东德秘密警察监听作家的故事"),
    
    # ===== Documentary =====
    Movie(movie_id="do01", title="地球脉动", genres=["纪录片"], duration=90, rating=9.8, year=2006,
          description="BBC 自然纪录片经典之作"),
]


def search_movies(
    genres: list[str] | None = None,
    max_duration: int = 999,
    min_rating: float = 0.0,
    exclude_genres: list[str] | None = None,
    exclude_ids: list[str] | None = None,
    limit: int = 10
) -> list[Movie]:
    """Search movies by criteria (MVP version, in-memory filter)."""
    results = []
    exclude_ids = exclude_ids or []
    exclude_genres = exclude_genres or []
    
    for movie in MOVIE_DATABASE:
        if movie.movie_id in exclude_ids:
            continue
        if movie.duration > max_duration:
            continue
        if movie.rating < min_rating:
            continue
        if genres and not any(g in movie.genres for g in genres):
            continue
        if exclude_genres and any(g in movie.genres for g in exclude_genres):
            continue
        results.append(movie)
    
    # Sort by rating desc, then by genre match count
    results.sort(key=lambda m: (
        -m.rating,
        -sum(1 for g in (genres or []) if g in m.genres),
        m.duration
    ))
    return results[:limit]


def get_movie_by_id(movie_id: str) -> Movie | None:
    """Get movie by ID."""
    for movie in MOVIE_DATABASE:
        if movie.movie_id == movie_id:
            return movie
    return None


def get_safe_pick() -> Movie:
    """Return the safest movie (high-rated comedy for R5 rule)."""
    comedies = [m for m in MOVIE_DATABASE if "喜剧" in m.genres and m.rating >= 8.0]
    comedies.sort(key=lambda m: -m.rating)
    return comedies[0] if comedies else MOVIE_DATABASE[0]
