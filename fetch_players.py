import requests
import json
import os
from datetime import datetime, timezone

SEASON   = "s10"
PLATFORM = "crossplay"

GCS_URL = "https://storage.googleapis.com/embark-discovery-leaderboard/leaderboard-crossplay-discovery-live.json"
API_BASE = f"https://api.the-finals-leaderboard.com/v1/leaderboard/{SEASON}/{PLATFORM}"

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

def find_exact(entries, tag):
    tag_lower = tag.lower().strip()
    for e in entries:
        name = e.get("name", "").lower().strip()
        if name == tag_lower:
            return e
    return None

def extract_gcs(entry):
    """GCS 필드: f=fame, r=rank, c=cashouts"""
    if not entry:
        return None, None, None
    return entry.get("f"), entry.get("r"), entry.get("c")

def extract_api(entry):
    """API 필드: fame/rankScore, rank, cashouts/totalCashouts"""
    if not entry:
        return None, None, None
    fame = entry.get("fame") if entry.get("fame") is not None else entry.get("rankScore")
    rank = entry.get("rank")
    cashouts = entry.get("cashouts") if entry.get("cashouts") is not None else entry.get("totalCashouts")
    return fame, rank, cashouts

def fetch_gcs():
    print("  [GCS] 접근 시도...")
    resp = requests.get(GCS_URL, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict):
        entries = None
        for v in data.values():
            if isinstance(v, list) and len(v) > 0:
                entries = v
                break
        if entries is None:
            entries = data
    else:
        entries = data
    if not isinstance(entries, list) or len(entries) == 0:
        raise ValueError("GCS 리스트 없음")
    print(f"  [GCS] 성공: {len(entries)}명")
    return entries

def fetch_api_single(tag):
    """커뮤니티 API로 특정 플레이어 조회"""
    url = f"{API_BASE}?name={requests.utils.quote(tag)}"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    entries = data.get("data", data) if isinstance(data, dict) else data
    if not isinstance(entries, list):
        return None
    # 완전 일치 우선
    tag_lower = tag.lower().strip()
    exact = next((e for e in entries if e.get("name","").lower().strip() == tag_lower), None)
    if exact:
        return exact, "API"
    # 없으면 첫 번째 결과
    if entries:
        return entries[0], "API-partial"
    return None, None

def main():
    players = load_json(PLAYERS_PATH, [])
    if not players:
        print("players.json이 비어있음. 종료.")
        return
    print(f"추적 대상 ({len(players)}명)")

    # GCS 전체 리더보드 로드 (실패해도 계속)
    gcs_entries = None
    try:
        gcs_entries = fetch_gcs()
    except Exception as e:
        print(f"  [GCS] 실패: {e} → 전체 API 폴백")

    history = load_json(HISTORY_PATH, {})
    now_iso = datetime.now(timezone.utc).isoformat()
    updated = []
    not_found = []

    for tag in players:
        fame, rank, cashouts, api_name, source = None, None, None, None, None

        # 1. GCS 완전 일치 시도
        if gcs_entries:
            entry = find_exact(gcs_entries, tag)
            if entry:
                fame, rank, cashouts = extract_gcs(entry)
                api_name = entry.get("name")
                source = "GCS"

        # 2. GCS 실패 시 API 개별 조회
        if fame is None:
            try:
                result = fetch_api_single(tag)
                if result and result[0]:
                    entry, source = result
                    fame, rank, cashouts = extract_api(entry)
                    api_name = entry.get("name")
            except Exception as e:
                print(f"  [API] {tag} 조회 실패: {e}")

        if fame is None:
            not_found.append(tag)
            print(f"  미등재: {tag}")
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
            print(f"  ✓ {msg}")
        else:
            print(f"  변화없음: {tag} fame={fame} [{source}]")

    save_json(HISTORY_PATH, history)
    print(f"\n완료. 변화 {len(updated)}건 / 미등재 {len(not_found)}명 / 전체 {len(players)}명")

if __name__ == "__main__":
    main()
