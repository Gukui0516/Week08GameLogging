## LogViz 사용 안내

이 리포지터리는 게임 로그를 집계/분석하는 간단한 파이썬 도구 모음입니다. 이 문서는 로컬에서 가상환경을 만들고 의존성을 설치한 뒤 프로그램을 실행하는 방법을 단계별로 설명합니다.

## 요구사항

- Python 3.10+ 권장(특정 바이너리 휠이 필요할 수 있음)
- Git, 인터넷 연결(의존성 설치 시)

필요한 파이썬 패키지는 프로젝트 루트의 `requirements.txt`에 정리되어 있습니다.

## 1) 가상환경 만들기 (bash 기반)

아래는 Windows 환경에서 기본 셸이 `bash.exe`(예: Git Bash)인 경우의 예시입니다.

1. 프로젝트 루트로 이동

```bash
cd /c/develop/logviz
```

2. 가상환경 생성

```bash
python -m venv .venv
```

3. 가상환경 활성화 (bash)

```bash
source .venv/Scripts/activate
# 활성화 후 프롬프트에 (.venv) 표시가 나옵니다
```

참고: WSL 또는 Linux/macOS에서는 `source .venv/bin/activate`를 사용합니다. PowerShell을 쓰는 경우 `.\.venv\Scripts\Activate.ps1`를 사용하세요.

## 2) 의존성 설치

가상환경을 활성화한 상태에서 아래 명령으로 의존성을 설치합니다.

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

주의: 일부 패키지(예: `pyarrow`, `numpy` 등)는 플랫폼/파이썬 버전에 맞는 바이너리 휠이 필요합니다. 설치 중 빌드 오류가 발생하면 아래 트러블슈팅을 참고하세요.

## 3) 데이터 구조

프로젝트는 기본적으로 `./DATA` 폴더에서 입력 파일을 찾습니다. 예시 구조:

```
DATA/
  2025-10-29/
    Player_1_20251029.csv
    Player_2_20251029.csv
    ...
```

CSV 파일은 플레이어별 원시 로그를 포함하며, `src/cache_manager.py`가 이를 로드/병합해 사용합니다.

## 4) CLI 사용법

메인 실행 파일은 루트의 `app_cli.py`입니다. 기본 사용 예시는 다음과 같습니다.

1. 전체 플레이어 처리하고 결과를 `./outputs`에 저장

```bash
python app_cli.py --data ./DATA --players all
```

2. 특정 플레이어들만 처리

```bash
python app_cli.py --data ./DATA --players player1,player2
```

3. 출력 경로 지정

```bash
python app_cli.py --data ./DATA --players all --out ./my_outputs
```

실행 후 출력 예시 파일들:

- `global_stage_means.csv` : 스테이지별 전역 평균값
- `personal_exit_counts.csv` : 플레이어별 포기(또는 종료) 카운트
- `first_grab_top3_by_stage.csv` : 각 스테이지별 First-Grab TOP3(정책: earliest)

## 5) 간단한 확인 방법

1. 스크립트 실행

```bash
python app_cli.py --data ./DATA --players all
```

2. `Saved to ./outputs` 메시지 확인
3. `outputs/` 디렉토리에 위의 CSV 파일들이 생성되었는지 확인

## 6) 트러블슈팅

- 의존성 설치 실패(PyArrow, NumPy 등):
  - Python 버전(3.10/3.11 권장)을 확인하세요.
  - 휠이 없어서 빌드가 필요한 경우 Visual C++ 빌드 도구(Windows) 또는 적절한 시스템 패키지를 설치해야 할 수 있습니다.
  - 가능한 경우 `pip install numpy --only-binary=:all:` 등 바이너리 설치를 시도하거나 conda 환경을 사용하세요.
- 권한/경로 문제: `outputs/` 디렉토리에 쓰기 권한이 있는지 확인하세요.
- 인코딩 문제: CSV 입출력 인코딩은 UTF-8로 지정되어 있습니다. 윈도우에서 Excel로 열 때 깨지면 Excel에서 UTF-8로 불러오기 옵션을 사용하세요.

## 7) (선택) Conda 사용 예

```bash
conda create -n logviz python=3.11 -y
conda activate logviz
pip install -r requirements.txt
```

## 8) 추가 정보

- 대시보드: `ui/dashboard.py` (Streamlit 기반으로 보임). Streamlit 대시보드를 실행하려면 의존성 설치 후 `streamlit run ui/dashboard.py`를 시도하세요.
- 코드 구조 요약:
  - `src/cache_manager.py` : 데이터 로딩/캐싱
  - `src/aggregator.py` : 집계 함수들
  - `app_cli.py` : 데이터 파이프라인을 실행하는 CLI

---

문의나 기능 추가 요청이 있으면 이 README를 업데이트해 주세요. 작은 예제 데이터나 기대 출력 샘플을 제공해 주시면 사용법 문서를 더 상세히 개선하겠습니다.
