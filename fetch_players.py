import requests
import json
import os
from datetime import datetime, timezone

SEASON   = "s10"
PLATFORM = "crossplay"

GCS_URL = "https://storage.googleapis.com/embark-discovery-leaderboard/leaderboard-crossplay-discovery-live.json"
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
    """완전 일치만 허용. #번호 포함 정확한 매칭."""
    tag_lower = tag.lower()
    return next((e for e in entries if e.get("name","").lower() == tag_lower), None)

def get_fame(entry):
    """
    가능한 모든 필드명 시도. 0도 유효한 값으로 처리.
    GCS는 'rs', 'rankScore', 'fame' 중 하나를 씀.
    """
    if entry is None:
        return None
    for key in ("fame", "rs", "rankScore", "rank_score", "score", "rankingScore", "points"):
        val = entry.get(key)
        if val is not None:
            return val
    return None

def get_rank(entry):
    if entry is None:
        return None
    for key in ("rank", "r", "position", "leaderboardRank"):
        val = entry.get(key)
        if val is not None:
            return val
    return None

def get_cashouts(entry):
    if entry is None:
        return None
    for key in ("cashouts", "c", "totalCashouts", "cash"):
        val = entry.get(key)
        if val is not None:
            return val
    return None

def fetch_gcs():
    print("  [GCS] 직접 접근 시도...")
    resp = requests.get(GCS_URL, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    # GCS 응답 구조 디버그 출력 (첫 실행 시 구조 파악용)
    if isinstance(data, dict):
        print(f"  [GCS] 최상위 키: {list(data.keys())[:10]}")
        entries = data.get("data") or data.get("leaderboard") or data.get("entries") or data.get("players")
        if entries is None:
            # 값이 리스트인 키 찾기
            for k, v in data.items():
                if isinstance(v, list) and len(v) > 0:
                    entries = v
                    print(f"  [GCS] 리스트 키 발견: '{k}' ({len(v)}개)")
                    break
        if entries is None:
            entries = data
    else:
        entries = data

    if not isinstance(entries, list) or len(entries) == 0:
        raise ValueError("GCS 응답에서 리스트 찾기 실패")

    # 첫 번째 엔트리 구조 출력 (필드명 파악)
    if entries:
        print(f"  [GCS] 샘플 엔트리 키: {list(entries[0].keys())}")
        print(f"  [GCS] 샘플 엔트리 값: {dict(list(entries[0].items())[:8])}")

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

    # API 샘플도 출력
    if entries:
        print(f"  [API] 샘플 엔트리 키: {list(entries[0].keys())}")
        print(f"  [API] 샘플 엔트리 값: {dict(list(entries[0].items())[:8])}")

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
        # 완전 일치만 허용
        entry    = find_player_exact(entries, tag)
        fame     = get_fame(entry)
        rank     = get_rank(entry)
        cashouts = get_cashouts(entry)
        api_name = entry.get("name") if entry else None

        if not entry:
            not_found_list.append(tag)
            print(f"  미등재(완전일치없음): {tag}")
            continue

        if fame is None:
            print(f"  ⚠ fame필드없음: {tag} | 엔트리: {dict(list(entry.items())[:6])}")
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
        print(f"  미등재 목록: {not_found_list}")

if __name__ == "__main__":
    main()
