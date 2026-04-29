import requests
import json
import os
from datetime import datetime, timezone

SEASON = "s10"
PLATFORM = "crossplay"
API_BASE = f"https://api.the-finals-leaderboard.com/v1/leaderboard/{SEASON}/{PLATFORM}"
HISTORY_PATH = "data/history.json"
PLAYERS_PATH = "players.json"
MAX_SNAPSHOTS = 200  # 태그당 최대 보관 스냅샷 수

def load_json(path, default):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def fetch_leaderboard():
    print(f"Fetching: {API_BASE}")
    resp = requests.get(API_BASE, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("data", data) if isinstance(data, dict) else data

def find_player(entries, tag):
    tag_lower = tag.lower()
    # 완전 일치 우선
    exact = next((e for e in entries if e.get("name","").lower() == tag_lower), None)
    if exact:
        return exact
    # 부분 일치 (해시 앞 닉네임)
    base = tag_lower.split("#")[0]
    return next((e for e in entries if e.get("name","").lower().startswith(base)), None)

def main():
    players = load_json(PLAYERS_PATH, [])
    if not players:
        print("players.json가 비어있음. 종료.")
        return

    print(f"추적 대상: {players}")

    try:
        entries = fetch_leaderboard()
        print(f"리더보드 항목 수: {len(entries)}")
    except Exception as e:
        print(f"API 오류: {e}")
        return

    history = load_json(HISTORY_PATH, {})
    now_iso = datetime.now(timezone.utc).isoformat()
    updated = []

    for tag in players:
        entry = find_player(entries, tag)
        snap = {
            "t": now_iso,
            "found": entry is not None,
            "rank": entry.get("rank") if entry else None,
            "fame": entry.get("fame") or entry.get("rankScore") if entry else None,
            "cashouts": entry.get("cashouts") or entry.get("totalCashouts") if entry else None,
            "name": entry.get("name") if entry else None,  # 실제 API 반환 닉네임 (변경 감지용)
        }

        if tag not in history:
            history[tag] = []

        prev_snaps = history[tag]
        prev_fame = prev_snaps[-1]["fame"] if prev_snaps else None

        # Fame이 바뀌었거나 첫 스냅샷일 때만 저장
        if not prev_snaps or prev_fame != snap["fame"]:
            history[tag].append(snap)
            history[tag] = history[tag][-MAX_SNAPSHOTS:]
            updated.append(f"{tag} ({prev_fame} → {snap['fame']})")
            print(f"  변화 감지: {tag} | rank={snap['rank']} fame={snap['fame']}")
        else:
            print(f"  변화 없음: {tag} | fame={snap['fame']}")

    save_json(HISTORY_PATH, history)
    print(f"\n완료. 변화 감지: {len(updated)}건")
    for u in updated:
        print(f"  - {u}")

if __name__ == "__main__":
    main()
