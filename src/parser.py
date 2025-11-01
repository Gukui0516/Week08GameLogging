# src/parser.py
from __future__ import annotations
from pathlib import Path
import pandas as pd
import numpy as np

HEADER_ALIASES = {
    "Timestamp": ["Timestamp", "Time", "시간", "타임스탬프", "ts", "date", "datetime"],
    "Event":     ["Event", "이벤트", "로깅 이벤트", "로그 이벤트"],
    "Level":     ["Level", "레벨", "로그 레벨"],
    "Key":       ["Key", "키", "항목", "이벤트키"],
    "Value":     ["Value", "값", "데이터", "파라미터"],
}

def filename_to_player_id(path: Path) -> str:
    return Path(path).stem

def _find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    lowers = {c.lower(): c for c in df.columns}
    for name in candidates:
        if name in df.columns:
            return name
        if name.lower() in lowers:
            return lowers[name.lower()]
    return None

def _coerce_timestamp(series: pd.Series) -> pd.Series:
    ts = pd.to_datetime(series, errors="coerce")
    if ts.isna().all():
        num = pd.to_numeric(series, errors="coerce")
        base = pd.Timestamp("1970-01-01")
        ts = base + pd.to_timedelta(num.fillna(0), unit="s")
    if ts.isna().all():
        base = pd.Timestamp("1970-01-01")
        idx = pd.RangeIndex(len(series))
        ts = base + pd.to_timedelta(idx, unit="s")
    return ts

def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    # 1) 우선 표준(대문자) 헤더로 맞춤
    colmap = {}
    for std, aliases in HEADER_ALIASES.items():
        found = _find_col(df, aliases)
        if found is not None:
            colmap[found] = std
    dfn = df.rename(columns=colmap).copy()

    # 2) 기본값 채우기
    if "Event" not in dfn.columns and "Key" in dfn.columns:
        dfn["Event"] = dfn["Key"]
    if "Level" not in dfn.columns:
        dfn["Level"] = "INFO"
    if "Key" not in dfn.columns:
        dfn["Key"] = ""
    if "Value" not in dfn.columns:
        dfn["Value"] = ""
    if "Timestamp" not in dfn.columns:
        base = pd.Timestamp("1970-01-01")
        dfn["Timestamp"] = base + pd.to_timedelta(range(len(dfn)), unit="s")
    else:
        dfn["Timestamp"] = _coerce_timestamp(dfn["Timestamp"])

    # 3) 문자열 정리
    for col in ["Event", "Level", "Key", "Value"]:
        dfn[col] = dfn[col].astype(str).str.strip().str.strip('"').str.strip("'")

    # 4) 소문자 표준으로 최종 리네이밍 (PlayerID는 나중에 주입)
    dfn = dfn.rename(columns={
        "Timestamp": "timestamp",
        "Event": "event",
        "Level": "level",
        "Key": "key",
        "Value": "value",
    })

    dfn.sort_values(["timestamp"], inplace=True, kind="mergesort")
    dfn.reset_index(drop=True, inplace=True)
    return dfn

def load_csv(path: Path, player_id: str | None = None) -> pd.DataFrame:
    path = Path(path)
    # on_bad_lines='skip': 잘못된 형식의 라인 건너뛰기 (pandas 1.3+)
    # encoding_errors='replace': 인코딩 오류 발생 시 대체 문자로 변환
    df = pd.read_csv(
        path, 
        encoding="utf-8",
        on_bad_lines='skip',
        encoding_errors='replace'
    )
    df = _normalize_columns(df)
    df["PlayerID"] = player_id or filename_to_player_id(path)
    return df

def load_dir(data_dir: Path, pattern: str = "*.csv") -> pd.DataFrame:
    data_dir = Path(data_dir)
    frames = []
    for p in data_dir.glob(pattern):
        try:
            frames.append(load_csv(p))
        except Exception as e:
            print(f"[parser] Skip {p.name}: {e}")
    if not frames:
        return pd.DataFrame(columns=["timestamp","event","level","key","value","PlayerID"])
    return pd.concat(frames, ignore_index=True)