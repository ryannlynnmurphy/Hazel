# -*- coding: utf-8 -*-
"""
JARVIS Search — Find anything in your conversation history

Usage:
  python3 search.py dentist appointment
  python3 search.py --date 2025-03-09
  python3 search.py --facts
  python3 search.py --stats
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from memory import search_conversations, get_all_facts, get_stats


def print_results(rows):
    if not rows:
        print("  No results found.")
        return
    for ts, role, content in rows:
        date = ts[:10]
        time_str = ts[11:16] if len(ts) > 16 else ""
        role_label = "YOU" if role == "user" else "JARVIS"
        print(f"\n  [{date} {time_str}] {role_label}:")
        print(f"  {content[:400]}")
        if len(content) > 400:
            print(f"  ... ({len(content)} chars total)")


def main():
    args = sys.argv[1:]

    if not args:
        print("Usage: python3 search.py <search terms>")
        print("       python3 search.py --date YYYY-MM-DD")
        print("       python3 search.py --facts")
        print("       python3 search.py --stats")
        return

    if args[0] == "--facts":
        facts = get_all_facts()
        if not facts:
            print("No facts stored yet.")
            return
        print("\nStored facts:")
        for cat, key, val in facts:
            print(f"  [{cat}] {key}: {val}")
        return

    if args[0] == "--stats":
        stats = get_stats()
        print("\nJARVIS Memory Stats:")
        for k, v in stats.items():
            print(f"  {k.replace('_', ' ').title()}: {v}")
        return

    if args[0] == "--date" and len(args) > 1:
        date_str = args[1]
        rows = search_conversations(date_str[:10])
        print(f"\nConversations from {date_str}:")
        print("─" * 50)
        print_results(rows)
        return

    # Regular search
    query = " ".join(args)
    rows = search_conversations(query)
    print(f"\nSearch results for: '{query}'")
    print("─" * 50)
    print_results(rows)
    print(f"\n  Found {len(rows)} result(s).")


if __name__ == "__main__":
    main()
import os
from tavily import TavilyClient

def web_search(query):
    try:
        api_key = os.getenv("TAVILY_API_KEY", "")
        if not api_key:
            return "No Tavily API key found."
        client = TavilyClient(api_key=api_key)
        result = client.search(query, search_depth="basic", max_results=3)
        answers = []
        if result.get("answer"):
            answers.append(result["answer"])
        for r in result.get("results", [])[:2]:
            answers.append(f"- {r['title']}: {r['content'][:200]}")
        return "\n".join(answers) if answers else "No results found."
    except Exception as e:
        return f"Search error: {str(e)}"
