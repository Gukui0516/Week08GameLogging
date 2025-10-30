from __future__ import annotations
import pandas as pd
import numpy as np


def build_segments(df: pd.DataFrame, assume_orphan_grab_counts_as_one: bool = True) -> pd.DataFrame:
    """
    게임 로그 DataFrame에서 스테이지 시도(세그먼트)를 추출하여 집계 정보를 생성합니다.
    
    Parameters:
    -----------
    df : pd.DataFrame
        파싱된 로그 DataFrame (컬럼: timestamp, event, level, key, value, PlayerID)
    assume_orphan_grab_counts_as_one : bool
        고아 Grab(InputGrabBreak 없이 종료된 Grab)을 1회로 간주할지 여부
    
    Returns:
    --------
    pd.DataFrame
        스테이지 시도별 집계 정보
        컬럼: PlayerID, stage, t_begin, t_end, cleared, 
              stage_play_time, clear_time, total_time,
              retry_cnt, exit_cnt, first_star, final_star,
              cam_move_cnt, cam_rotate_cnt, cam_pan_cnt, cam_total_cnt,
              grab_pair_cnt, pushpull_cnt, first_grab_object
    """
    
    if df is None or df.empty:
        return _empty_segments_df()
    
    df = df.sort_values(["timestamp"], kind="mergesort").reset_index(drop=True)
    
    segments = []
    current_seg = None
    
    for idx, row in df.iterrows():
        event = str(row["event"]).strip()
        value = str(row["value"]).strip() if pd.notna(row["value"]) else ""
        timestamp = row["timestamp"]
        
        # StageBegin: 새 세그먼트 시작
        if event == "StageBegin":
            # 이전 세그먼트가 열려있으면 강제 마감 (다른 스테이지 Begin 감지)
            if current_seg is not None:
                current_seg["t_end"] = timestamp
                current_seg["cleared"] = False
                _finalize_segment(current_seg, df, assume_orphan_grab_counts_as_one)
                segments.append(current_seg)
            
            # 새 세그먼트 초기화
            current_seg = {
                "PlayerID": row["PlayerID"],
                "stage": _normalize_stage_name(value),
                "t_begin": timestamp,
                "t_end": None,
                "cleared": False,
                "start_idx": idx,
                "end_idx": None,
                "last_retry_idx": None,
            }
        
        # 세그먼트가 열려있을 때만 처리
        elif current_seg is not None:
            stage_norm = _normalize_stage_name(value)
            
            # StageClear: 세그먼트 종료 (스테이지명 매칭)
            if event == "StageClear" and stage_norm == current_seg["stage"]:
                current_seg["t_end"] = timestamp
                current_seg["end_idx"] = idx
                current_seg["cleared"] = True
                _finalize_segment(current_seg, df, assume_orphan_grab_counts_as_one)
                segments.append(current_seg)
                current_seg = None
            
            # StageExit: 세그먼트 포기로 종료
            elif event == "StageExit":
                current_seg["t_end"] = timestamp
                current_seg["end_idx"] = idx
                current_seg["cleared"] = False
                _finalize_segment(current_seg, df, assume_orphan_grab_counts_as_one)
                segments.append(current_seg)
                current_seg = None
            
            # StageRetry: 마지막 리트라이 인덱스 기록
            elif event == "StageRetry":
                current_seg["last_retry_idx"] = idx
    
    # 파일 끝에서 미완 세그먼트 마감
    if current_seg is not None:
        current_seg["t_end"] = df.iloc[-1]["timestamp"]
        current_seg["end_idx"] = len(df) - 1
        current_seg["cleared"] = False
        _finalize_segment(current_seg, df, assume_orphan_grab_counts_as_one)
        segments.append(current_seg)
    
    if not segments:
        return _empty_segments_df()
    
    return pd.DataFrame(segments)


def _finalize_segment(seg: dict, df: pd.DataFrame, assume_orphan_grab: bool):
    """세그먼트 집계 정보를 계산합니다."""
    
    start_idx = seg["start_idx"]
    end_idx = seg["end_idx"] if seg["end_idx"] is not None else len(df) - 1
    
    # 세그먼트 윈도우 추출
    window = df.iloc[start_idx:end_idx + 1].copy()
    
    # === 시간 계산 ===
    t_begin = seg["t_begin"]
    t_end = seg["t_end"]
    
    # total_time: Begin부터 종료까지 (Clear든 Exit이든)
    if t_end is not None and t_begin is not None:
        seg["total_time"] = (t_end - t_begin).total_seconds()
    else:
        seg["total_time"] = None
    
    # stage_play_time: StageBegin부터 클리어까지 (클리어된 경우만)
    if seg["cleared"] and t_end is not None and t_begin is not None:
        seg["stage_play_time"] = (t_end - t_begin).total_seconds()
    else:
        seg["stage_play_time"] = None
    
    # clear_time: 마지막 Retry부터 클리어까지 (Retry 고려)
    if seg["cleared"]:
        last_retry_idx = seg.get("last_retry_idx")
        if last_retry_idx is not None:
            # 마지막 Retry 시각부터 Clear까지
            t_retry = df.iloc[last_retry_idx]["timestamp"]
            seg["clear_time"] = (t_end - t_retry).total_seconds()
        else:
            # Retry 없으면 Begin부터 Clear까지 (stage_play_time과 동일)
            seg["clear_time"] = (t_end - t_begin).total_seconds()
    else:
        seg["clear_time"] = None
    
    # === 리트라이 횟수 ===
    seg["retry_cnt"] = len(window[window["event"] == "StageRetry"])
    
    # === 포기 횟수 ===
    seg["exit_cnt"] = 1 if not seg["cleared"] and seg["end_idx"] is not None else 0
    
    # === 별 (StageStar) ===
    star_rows = window[window["event"] == "StageStar"].copy()
    if not star_rows.empty:
        star_values = pd.to_numeric(star_rows["value"], errors="coerce")
        seg["first_star"] = star_values.iloc[0] if len(star_values) > 0 else None
        seg["final_star"] = star_values.iloc[-1] if len(star_values) > 0 else None
    else:
        seg["first_star"] = None
        seg["final_star"] = None
    
    # === 카메라 조작 ===
    seg["cam_move_cnt"] = len(window[window["event"] == "CameraZoom"])
    seg["cam_rotate_cnt"] = len(window[window["event"] == "CameraRotate"])
    seg["cam_pan_cnt"] = len(window[window["event"] == "CameraPanning"])
    seg["cam_total_cnt"] = seg["cam_move_cnt"] + seg["cam_rotate_cnt"] + seg["cam_pan_cnt"]
    
    # === 그랩 세트 (InputGrab ~ InputGrabBreak) ===
    seg["grab_pair_cnt"] = _count_grab_pairs(window, assume_orphan_grab)
    
    # === 밀·당 ===
    seg["pushpull_cnt"] = len(window[window["event"] == "InputPushPull"])
    
    # === 첫 그랩 오브젝트 (root 제외) ===
    grab_rows = window[window["event"] == "InputGrab"].copy()
    if not grab_rows.empty:
        non_root = grab_rows[grab_rows["value"].astype(str).str.strip().str.lower() != "root"]
        seg["first_grab_object"] = non_root.iloc[0]["value"] if not non_root.empty else None
    else:
        seg["first_grab_object"] = None
    
    # 임시 키 제거
    seg.pop("start_idx", None)
    seg.pop("end_idx", None)
    seg.pop("last_retry_idx", None)


def _count_grab_pairs(window: pd.DataFrame, assume_orphan_grab: bool) -> int:
    """
    InputGrab ~ InputGrabBreak 쌍의 개수를 센다.
    고아 Grab(Break 없이 종료)은 assume_orphan_grab=True이면 1회로 간주.
    """
    grab_events = window[window["event"].isin(["InputGrab", "InputGrabBreak"])].copy()
    
    if grab_events.empty:
        return 0
    
    count = 0
    open_grabs = 0
    
    for _, row in grab_events.iterrows():
        if row["event"] == "InputGrab":
            open_grabs += 1
        elif row["event"] == "InputGrabBreak":
            if open_grabs > 0:
                count += 1
                open_grabs -= 1
    
    # 고아 Grab 처리
    if assume_orphan_grab and open_grabs > 0:
        count += open_grabs
    
    return count


def _empty_segments_df() -> pd.DataFrame:
    """빈 세그먼트 DataFrame을 반환합니다."""
    return pd.DataFrame(columns=[
        "PlayerID", "stage", "t_begin", "t_end", "cleared",
        "stage_play_time", "clear_time", "total_time", 
        "retry_cnt", "exit_cnt",
        "first_star", "final_star",
        "cam_move_cnt", "cam_rotate_cnt", "cam_pan_cnt", "cam_total_cnt",
        "grab_pair_cnt", "pushpull_cnt", "first_grab_object",
    ])


def _normalize_stage_name(stage_name: str) -> str:
    """
    스테이지명을 정규화합니다.
    - NBSP(\xa0)를 일반 공백으로 변환
    - 앞뒤 공백 제거
    - 소문자로 변환
    """
    if pd.isna(stage_name):
        return ""
    return str(stage_name).replace('\xa0', ' ').strip().lower()