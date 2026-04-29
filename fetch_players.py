import requests
import json
import os
from datetime import datetime, timezone

# ── 설정 ──────────────────────────────────────────────
SEASON   = "s10"
PLATFORM = "crossplay"

# 소스 1: Embark GCS 직접 (캐시 없음, 최우선)
GCS_URL = "https://storage.googleapis.com/embark-discovery-leaderboard/leaderboard-crossplay-discovery-live.json"

# 소스 2: 커뮤니티 API (폴백)
API_URL = f"https://api.the-finals-leaderboard.com/v1/leaderboard/{SEASON}/{PLATFORM}"

HISTORY_PATH  = "data/history.json"
PLAYERS_PATH  = "players.json"
MAX_SNAPSHOTS = 500

def load_json(path, default):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default

def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'))

def find_player(entries, tag):
    tag_lower = tag.lower()
    exact = next((e for e in entries if e.get("name","").lower() == tag_lower), None)
    if exact:
        return exact
    base = tag_lower.split("#")[0]
    return next((e for e in entries if e.get("name","").lower().startswith(base)), None)

def fetch_gcs():
    print("  [GCS] 직접 접근 시도...")
    resp = requests.get(GCS_URL, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    entries = data.get("data", data) if isinstance(data, dict) else data
    if not isinstance(entries, list) or len(entries) == 0:
        raise ValueError("GCS 응답이 비어있음")
    print(f"  [GCS] 성공: {len(entries)}명")
    return entries, "GCS"

def fetch_api():
    print("  [API] 커뮤니티 API 시도...")
    resp = requests.get(API_URL, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    entries = data.get("data", data) if isinstance(data, dict) else data
    if not isinstance(entries, list) or len(entries) == 0:
        raise ValueError("API 응답이 비어있음")
    print(f"  [API] 성공: {len(entries)}명")
    return entries, "API"

def fetch_leaderboard():
    try:
        return fetch_gcs()
    except Exception as e:
        print(f"  [GCS] 실패: {e}")
        try:
            return fetch_api()
        except Exception as e2:
            raise RuntimeError(f"GCS·API 모두 실패: {e2}")

def main():
    players = load_json(PLAYERS_PATH, [])
    if not players:
        print("players.json이 비어있음. 종료.")
        return
    print(f"추적 대상 ({len(players)}명): {players}")

    try:
        entries, source = fetch_leaderboard()
    except Exception as e:
        print(f"리더보드 로드 실패: {e}")
        return

    history = load_json(HISTORY_PATH, {})
    now_iso = datetime.now(timezone.utc).isoformat()
    updated = []

    for tag in players:
        entry    = find_player(entries, tag)
        fame     = entry.get("fame") or entry.get("rankScore") or entry.get("rank_score") if entry else None
        rank     = entry.get("rank") if entry else None
        cashouts = entry.get("cashouts") or entry.get("totalCashouts") if entry else None
        api_name = entry.get("name") if entry else None

        snap = {"t": now_iso, "src": source, "found": entry is not None,
                "rank": rank, "fame": fame, "cashouts": cashouts, "name": api_name}

        if tag not in history:
            history[tag] = []

        prev_fame = history[tag][-1]["fame"] if history[tag] else None

        if not history[tag] or prev_fame != fame:
            history[tag].append(snap)
            history[tag] = history[tag][-MAX_SNAPSHOTS:]
            msg = f"{tag}: {prev_fame} → {fame} (rank={rank}) [{source}]"
            updated.append(msg)
            print(f"  변화: {msg}")
        else:
            print(f"  변화없음: {tag} fame={fame} [{source}]")

    save_json(HISTORY_PATH, history)
    print(f"\n완료. 변화 {len(updated)}건 / {len(players)}명")

if __name__ == "__main__":
    main()
