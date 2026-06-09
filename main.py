#!/usr/bin/env python3
"""
Social Consensus Agent - Final Demo Entry Point
Supports: N users, LLM (DeepSeek/Mock), Chroma/Memory vector store, MCP tools.

Usage:
    python main.py                    # Run all demo scenarios
    python main.py --scenario 1       # Run specific scenario
    python main.py --n 4              # 4-person group demo
    python main.py --custom           # Interactive mode
    python main.py --llm deepseek     # Use DeepSeek LLM (needs API key)
    python main.py --chroma           # Use Chroma vector store
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))

from src.graph.consensus_graph import build_consensus_workflow
from src.llm.mock import create_llm
from src.memory.vector_store import create_vector_store


# ===== Demo Scenarios (N-person) =====

SCENARIOS = {
    1: {
        "name": "经典冲突：科幻 vs 喜剧 (2人)",
        "users": {
            "Alice": "我喜欢科幻片，时长不要超过120分钟，不要恐怖片",
            "Bob": "我想看喜剧片，轻松一点的，时长90分钟以内最好",
        }
    },
    2: {
        "name": "恐怖片红线 (2人)",
        "users": {
            "Alice": "我想看悬疑惊悚片，越刺激越好",
            "Bob": "我害怕恐怖片和惊悚片，想看爱情片或者剧情片，不要超过2小时",
        }
    },
    3: {
        "name": "高要求 vs 随意 (2人)",
        "users": {
            "Alice": "我只看高分电影，评分至少8分以上，科幻或剧情都可以",
            "Bob": "我随便，什么都行，搞笑的最好",
        }
    },
    4: {
        "name": "宿舍4人：多目标博弈",
        "users": {
            "Alice": "我喜欢科幻和动作片，评分高的，不要太长",
            "Bob": "我只看喜剧和动画片，超过100分钟的不行",
            "Carol": "我要看爱情片或者剧情片，拒绝恐怖和战争",
            "David": "我都可以，最好是大家都喜欢的，评分8分以上",
        }
    },
    5: {
        "name": "家庭6人：代际差异",
        "users": {
            "爷爷": "我想看战争片或者历史剧情片",
            "奶奶": "爱情片或者家庭剧都可以，不要太悲伤",
            "爸爸": "动作片或者悬疑片，刺激一点的",
            "妈妈": "喜剧片最好，全家人一起笑",
            "哥哥": "科幻大片，特效好的，越长越好",
            "妹妹": "动画片或者爱情片，不要超过2小时",
        }
    },
}


def run_scenario(sid: int, llm_name: str = "mock", use_chroma: bool = False) -> None:
    if sid not in SCENARIOS:
        print(f"Invalid scenario: {sid}. Available: {list(SCENARIOS.keys())}")
        return
    s = SCENARIOS[sid]
    print(f"\n{'#'*60}")
    print(f"# Scenario {sid}: {s['name']}")
    print(f"{'#'*60}")

    llm = create_llm() if llm_name != "none" else None
    vector_store = create_vector_store() if use_chroma else None
    state = build_consensus_workflow(s["users"], llm=llm, vector_store=vector_store)

    _print_result(state, s["users"])


def run_all_scenarios(llm_name: str = "mock", use_chroma: bool = False) -> None:
    print("\n" + "="*60)
    print("  Social Consensus Agent - Final Demo")
    print("  所有场景演示")
    print("="*60)
    for sid in sorted(SCENARIOS.keys()):
        run_scenario(sid, llm_name, use_chroma)
        print("\n" + "-"*60)
    print("\n所有场景演示完成！")


def interactive_n_person(llm_name: str = "mock", use_chroma: bool = False) -> None:
    print("\n" + "="*60)
    print("  Social Consensus Agent - 交互模式 (支持 N 人)")
    print("="*60)

    n = input("群体人数 (默认2): ").strip()
    n = int(n) if n.isdigit() and int(n) > 0 else 2

    users = {}
    for i in range(n):
        name = input(f"第{i+1}人名字 (默认User{i+1}): ").strip() or f"User{i+1}"
        prefs = input(f"  {name} 的偏好: ").strip() or "随便都可以"
        users[name] = prefs

    llm = create_llm() if llm_name != "none" else None
    vector_store = create_vector_store() if use_chroma else None
    state = build_consensus_workflow(users, llm=llm, vector_store=vector_store)
    _print_result(state, users)


def _print_result(state, users: dict) -> None:
    print(f"\n--- 协商日志 ({len(state.log)} 步) ---")
    for entry in state.log:
        print(f"  {entry}")

    if state.result:
        r = state.result
        m = r.movie
        print(f"\n{'='*60}")
        print(f"  最终推荐: 《{m.title}》")
        print(f"  类型: {m.genres} | 时长: {m.duration}min | 评分: {m.rating}/10")
        print(f"  群体满意度: {r.group_score:.1f}/10 | 轮次: {r.rounds_taken}")
        print(f"  参与人数: {len(users)}人")
        if r.is_fallback:
            print(f"  [安全牌推荐]")
        if r.dissenters:
            print(f"  异议: {', '.join(r.dissenters)}")
        print(f"{'='*60}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Social Consensus Agent - Final Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                    # All scenarios (mock mode)
  python main.py --scenario 4       # 4-person dorm scenario
  python main.py --scenario 5       # 6-person family scenario
  python main.py --custom           # Interactive N-person mode
  python main.py --llm deepseek     # Use DeepSeek API (needs DEEPSEEK_API_KEY)
  python main.py --chroma           # Enable Chroma vector store
        """
    )
    parser.add_argument("--scenario", type=int, choices=[1,2,3,4,5],
                       help="Run specific scenario (1-5)")
    parser.add_argument("--custom", action="store_true",
                       help="Interactive mode")
    parser.add_argument("--llm", choices=["mock", "deepseek", "none"],
                       default="mock", help="LLM provider (default: mock)")
    parser.add_argument("--chroma", action="store_true",
                       help="Enable Chroma vector store")

    args = parser.parse_args()

    if args.custom:
        interactive_n_person(args.llm, args.chroma)
    elif args.scenario:
        run_scenario(args.scenario, args.llm, args.chroma)
    else:
        run_all_scenarios(args.llm, args.chroma)


if __name__ == "__main__":
    main()
