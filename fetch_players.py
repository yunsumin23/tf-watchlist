import requests
import json
import os
from datetime import datetime, timezone

SEASON   = "s10"
PLATFORM = "crossplay"

# GCS 직접 접근 (캐시 없음, 최우선)
# 필드명: f=fame, r=rank, c=cashouts, name=name
GCS_URL = "https://storage.googleapis.com/embark-discovery-leaderboard/leaderboard-crossplay-discovery-live.json"

# 커뮤니티 API (폴백)
# 필드명: fame, rank, cashouts, name
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

def find_player_exact(entries, tag):
    """완전 일치만. 대소문자 무시."""
    tag_lower = tag.lower()
    return next((e for e in entries if e.get("name","").lower() == tag_lower), None)

def extract_fields(entry, source):
    """소스에 따라 올바른 필드명으로 값 추출."""
    if entry is None:
        return None, None, None, None
    if source == "GCS":
        # GCS 필드: f, r, c, name
        fame     = entry.get("f")
        rank     = entry.get("r")
        cashouts = entry.get("c")
    else:
        # API 필드: fame, rank, cashouts
        fame     = entry.get("fame") if entry.get("fame") is not None else entry.get("rankScore")
        rank     = entry.get("rank")
        cashouts = entry.get("cashouts") if entry.get("cashouts") is not None else entry.get("totalCashouts")
    api_name = entry.get("name")
    return fame, rank, cashouts, api_name

def fetch_gcs():
    print("  [GCS] 직접 접근 시도...")
    resp = requests.get(GCS_URL, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict):
        entries = data.get("data") or data.get("leaderboard") or data.get("entries") or data.get("players")
        if entries is None:
            for v in data.values():
                if isinstance(v, list) and len(v) > 0:
                    entries = v
                    break
    else:
        entries = data
    if not isinstance(entries, list) or len(entries) == 0:
        raise ValueError("GCS 응답에서 리스트 찾기 실패")
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
    not_found_list = []

    for tag in players:
        entry = find_player_exact(entries, tag)
        fame, rank, cashouts, api_name = extract_fields(entry, source)

        if not entry:
            not_found_list.append(tag)
            print(f"  미등재: {tag}")
            continue

        if fame is None:
            print(f"  ⚠ fame없음: {tag}")
            continue

        snap = {
            "t": now_iso, "src": source,
            "found": True,
            "rank": rank, "fame": fame,
            "cashouts": cashouts, "name": api_name
        }

        if tag not in history:
            history[tag] = []

        prev_valid = next((s for s in reversed(history[tag]) if s.get("fame") is not None), None)
        prev_fame = prev_valid["fame"] if prev_valid else None

        if prev_fame is None or prev_fame != fame:
            history[tag].append(snap)
            history[tag] = history[tag][-MAX_SNAPSHOTS:]
            msg = f"{tag}: {prev_fame} → {fame} (rank={rank}) [{source}]"
            updated.append(msg)
            print(f"  ✓ 변화: {msg}")
        else:
            print(f"  변화없음: {tag} fame={fame} [{source}]")

    save_json(HISTORY_PATH, history)
    print(f"\n완료. 변화 {len(updated)}건 / 미등재 {len(not_found_list)}명 / 전체 {len(players)}명")
    if not_found_list:
        print(f"  미등재: {not_found_list}")

if __name__ == "__main__":
    main()
