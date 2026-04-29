# THE FINALS — WATCHLIST

핵쟁이 플레이어 추적 도구. GitHub Actions가 15분마다 Embark 리더보드를 자동 폴링하여 `data/history.json`에 기록합니다.

## 파일 구조

```
tf-watchlist/
├── .github/workflows/fetch.yml   # GitHub Actions 워크플로우
├── data/
│   └── history.json              # 자동 생성, 플레이어별 스냅샷 기록
├── fetch_players.py              # 폴링 스크립트
├── players.json                  # 추적할 플레이어 태그 목록
└── README.md
```

## 사용 방법

1. `players.json`에 추적할 Embark 태그 추가
2. GitHub Actions가 15분마다 자동 실행
3. HTML 앱에서 GitHub 유저명/레포명 입력 후 "히스토리 가져오기"

## players.json 형식

```json
["NL#4631", "OP#8009"]
```

## GitHub Actions 권한 설정

레포 Settings → Actions → General → Workflow permissions
→ **Read and write permissions** 선택 후 저장
