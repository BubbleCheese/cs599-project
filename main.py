#!/usr/bin/env python3
"""
Social Consensus Agent - MVP Entry Point
Core closed-loop demo: 2 virtual users + 1 Mediator Agent
Negotiation dimensions: genre + duration

Usage:
    python main.py              # Run default demo scenarios
    python main.py --scenario 1 # Run specific scenario (1-4)
    python main.py --custom     # Interactive mode: input your own preferences
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.graph.consensus_graph import build_consensus_workflow


# ===== Demo Scenarios =====

SCENARIOS = {
    1: {
        "name": "经典冲突：科幻爱好者 vs 喜剧爱好者",
        "users": {
            "Alice": "我喜欢科幻片，时长不要超过120分钟，不要恐怖片",
            "Bob": "我想看喜剧片，轻松一点的，时长90分钟以内最好"
        }
    },
    2: {
        "name": "恐怖片红线：一方绝对不接受",
        "users": {
            "Alice": "我想看悬疑惊悚片，越刺激越好",
            "Bob": "我害怕恐怖片和惊悚片，想看爱情片或者剧情片，不要超过2小时"
        }
    },
    3: {
        "name": "高要求 vs 随意：评分敏感",
        "users": {
            "Alice": "我只看高分电影，评分至少8分以上，科幻或剧情都可以",
            "Bob": "我随便，什么都行，搞笑的最好"
        }
    },
    4: {
        "name": "极端冲突：几乎无交集",
        "users": {
            "Alice": "我要看科幻大片，越长越好，星际穿越那种",
            "Bob": "我只看90分钟以内的喜剧或者动画片，不要科幻"
        }
    },
}


def run_scenario(scenario_id: int) -> None:
    """Run a single demo scenario."""
    if scenario_id not in SCENARIOS:
        print(f"Invalid scenario ID: {scenario_id}. Available: {list(SCENARIOS.keys())}")
        return
    
    scenario = SCENARIOS[scenario_id]
    print(f"\n{'#'*60}")
    print(f"# Scenario {scenario_id}: {scenario['name']}")
    print(f"{'#'*60}")
    
    for name, text in scenario["users"].items():
        print(f"  {name}: \"{text}\"")
    print()
    
    state = build_consensus_workflow(scenario["users"])
    
    # Print negotiation log summary
    print(f"\n--- 协商过程日志 ({len(state.log)} 步) ---")
    for entry in state.log:
        print(f"  {entry}")
    
    if state.result:
        print(f"\n--- 最终结果 ---")
        print(f"  推荐影片: 《{state.result.movie.title}》")
        print(f"  影片类型: {state.result.movie.genres}")
        print(f"  影片时长: {state.result.movie.duration}分钟")
        print(f"  豆瓣评分: {state.result.movie.rating}/10")
        print(f"  群体满意度: {state.result.group_score:.1f}/10")
        print(f"  协商轮次: {state.result.rounds_taken}")
        if state.result.is_fallback:
            print(f"  [安全牌推荐: 所有妥协规则均失败]")
        if state.result.dissenters:
            print(f"  异议成员: {', '.join(state.result.dissenters)}")


def run_all_scenarios() -> None:
    """Run all demo scenarios."""
    print("\n" + "="*60)
    print("  Social Consensus Agent - MVP Core Loop Demo")
    print("  群体协商观影 Agent - 核心闭环演示")
    print("="*60)
    
    for sid in sorted(SCENARIOS.keys()):
        run_scenario(sid)
        print("\n" + "-"*60)
    
    print("\n所有场景演示完成！")


def interactive_mode() -> None:
    """Interactive mode: user inputs their own preferences."""
    print("\n" + "="*60)
    print("  Social Consensus Agent - 交互模式")
    print("="*60)
    print("  输入两位成员的观影偏好，Agent 将协商出推荐方案。\n")
    
    users = {}
    users["Alice"] = input("Alice 的偏好描述: ").strip() or "我想看科幻片，不要恐怖片"
    users["Bob"] = input("Bob 的偏好描述: ").strip() or "我想看喜剧片，时长短一点"
    
    print()
    state = build_consensus_workflow(users)
    
    if state.result:
        print(f"\n{'='*60}")
        print(f"  最终推荐: 《{state.result.movie.title}》")
        print(f"  类型: {state.result.movie.genres}")
        print(f"  时长: {state.result.movie.duration}分钟")
        print(f"  评分: {state.result.movie.rating}/10")
        print(f"  满意度: {state.result.group_score:.1f}/10")
        print(f"{'='*60}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Social Consensus Agent - MVP Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py              # Run all 4 demo scenarios
  python main.py --scenario 1 # Run scenario 1 only
  python main.py --custom     # Interactive mode
        """
    )
    parser.add_argument("--scenario", type=int, choices=[1,2,3,4],
                       help="Run specific scenario (1-4)")
    parser.add_argument("--custom", action="store_true",
                       help="Interactive mode: input your own preferences")
    
    args = parser.parse_args()
    
    if args.custom:
        interactive_mode()
    elif args.scenario:
        run_scenario(args.scenario)
    else:
        run_all_scenarios()


if __name__ == "__main__":
    main()
