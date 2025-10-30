from __future__ import annotations
import pandas as pd
import numpy as np
from .segment_builder import build_segments

def global_stage_means(segs: pd.DataFrame) -> pd.DataFrame:
    if segs is None or segs.empty:
        return pd.DataFrame(columns=[
            "stage","n_players_used","mean_stage_play_time","mean_clear_time",
            "mean_first_clear_star",
            "mean_retry","mean_cam_total","mean_cam_move","mean_cam_rotate","mean_cam_pan",
            "mean_grab_pair","mean_pushpull"
        ])
    g = {}
    g["n_players_used"]       = segs.groupby("stage")["PlayerID"].nunique()
    g["mean_stage_play_time"] = segs.groupby("stage")["stage_play_time"].mean(numeric_only=True)
    g["mean_clear_time"]      = segs.groupby("stage")["clear_time"].mean(numeric_only=True)

    # 각 플레이어의 스테이지별 '첫 클리어'에서 받은 별만 평균
    cleared_segs = segs[(segs["cleared"] == True) & segs["first_star"].notna()].copy()
    if not cleared_segs.empty:
        cleared_segs = cleared_segs.sort_values(["PlayerID", "stage", "t_end"], kind="mergesort")
        first_clears = cleared_segs.groupby(["PlayerID", "stage"]).first()["first_star"].reset_index()
        g["mean_first_clear_star"] = first_clears.groupby("stage")["first_star"].mean(numeric_only=True)
    else:
        g["mean_first_clear_star"] = pd.Series(dtype=float)

    g["mean_retry"]           = segs.groupby("stage")["retry_cnt"].mean(numeric_only=True)
    g["mean_cam_move"]        = segs.groupby("stage")["cam_move_cnt"].mean(numeric_only=True)
    g["mean_cam_rotate"]      = segs.groupby("stage")["cam_rotate_cnt"].mean(numeric_only=True)
    g["mean_cam_pan"]         = segs.groupby("stage")["cam_pan_cnt"].mean(numeric_only=True)
    g["mean_cam_total"]       = segs.groupby("stage")["cam_total_cnt"].mean(numeric_only=True)
    g["mean_grab_pair"]       = segs.groupby("stage")["grab_pair_cnt"].mean(numeric_only=True)
    g["mean_pushpull"]        = segs.groupby("stage")["pushpull_cnt"].mean(numeric_only=True)

    out = pd.concat(g, axis=1).reset_index()
    out.columns.name = None
    return out

def global_stage_exit_counts(segs: pd.DataFrame, selected_players: list[str] | None) -> pd.DataFrame:
    if segs is None or segs.empty:
        return pd.DataFrame(columns=["stage","exit_sum"])
    df = segs
    if selected_players:
        df = df[df["PlayerID"].isin(selected_players)]
    out = df.groupby("stage")["exit_cnt"].sum(min_count=1).reset_index()
    out.rename(columns={"exit_cnt":"exit_sum"}, inplace=True)
    out["exit_sum"] = out["exit_sum"].fillna(0).astype(int)
    return out

def personal_stage_exit_counts(segs: pd.DataFrame, selected_players: list[str] | None) -> pd.DataFrame:
    if segs is None or segs.empty:
        return pd.DataFrame(columns=["PlayerID","stage","exit_sum"])
    df = segs
    if selected_players:
        df = df[df["PlayerID"].isin(selected_players)]
    out = df.groupby(["PlayerID","stage"])["exit_cnt"].sum(min_count=1).reset_index()
    out.rename(columns={"exit_cnt":"exit_sum"}, inplace=True)
    out["exit_sum"] = out["exit_sum"].fillna(0).astype(int)
    return out

def earliest_3_distinct_grabs_for_stage_with_policy(
    raw_all: pd.DataFrame,
    stage: str,
    selected_players: list[str] | None,
    policy: str = "earliest",  # earliest | latest | shortest_clear
    exclude_roots: bool = True,
) -> pd.DataFrame:
    if raw_all is None or raw_all.empty or not stage:
        return pd.DataFrame(columns=["rank","object_name","timestamp","dt_from_begin","PlayerID"])
    df = raw_all.copy()
    if selected_players:
        df = df[df["PlayerID"].isin(selected_players)]
    if df.empty:
        return pd.DataFrame(columns=["rank","object_name","timestamp","dt_from_begin","PlayerID"])

    segs = build_segments(df)
    segs = segs[(segs["stage"] == stage) & segs["t_end"].notna()].copy()
    if segs.empty:
        return pd.DataFrame(columns=["rank","object_name","timestamp","dt_from_begin","PlayerID"])

    seg = _pick_segment_by_policy(segs, policy)
    pid = seg["PlayerID"]; t0 = seg["t_begin"]; t1 = seg["t_end"]

    win = df[(df["PlayerID"] == pid) & (df["timestamp"] >= t0) & (df["timestamp"] <= t1)].copy()
    grabs = win[win["event"] == "InputGrab"].copy()
    if exclude_roots:
        grabs = grabs[grabs["value"].astype(str).str.strip().str.lower() != "root"]
    if grabs.empty:
        return pd.DataFrame(columns=["rank","object_name","timestamp","dt_from_begin","PlayerID"])

    grabs = grabs.sort_values("timestamp", kind="mergesort")
    firsts = grabs.drop_duplicates(subset=["value"], keep="first").head(3).copy()
    firsts["dt_from_begin"] = (firsts["timestamp"] - t0).dt.total_seconds()
    firsts["rank"] = range(1, len(firsts) + 1)
    firsts.rename(columns={"value":"object_name"}, inplace=True)
    firsts["PlayerID"] = pid
    return firsts[["rank","object_name","timestamp","dt_from_begin","PlayerID"]]

def _pick_segment_by_policy(segs: pd.DataFrame, policy: str) -> dict:
    s = segs.copy()
    s = s.sort_values(["t_end","t_begin"], kind="mergesort")
    if policy == "earliest":
        seg = s.iloc[s["t_end"].values.argmin()]
    elif policy == "latest":
        seg = s.iloc[s["t_end"].values.argmax()]
    elif policy == "shortest_clear":
        cleared = s[(s["cleared"] == True) & s["clear_time"].notna()].copy()
        if not cleared.empty:
            seg = cleared.iloc[cleared["clear_time"].astype(float).values.argmin()]
        else:
            seg = s.iloc[s["t_end"].values.argmax()]
    else:
        seg = s.iloc[s["t_end"].values.argmax()]
    return seg.to_dict()

def personal_first_clear_stars(segs: pd.DataFrame, selected_players: list[str] | None) -> pd.DataFrame:
    """각 플레이어의 스테이지별 첫 클리어 시 받은 별"""
    if segs is None or segs.empty:
        return pd.DataFrame(columns=["PlayerID","stage","first_clear_star"])
    df = segs
    if selected_players:
        df = df[df["PlayerID"].isin(selected_players)]
    cleared = df[(df["cleared"] == True) & df["first_star"].notna()].copy()
    if cleared.empty:
        return pd.DataFrame(columns=["PlayerID","stage","first_clear_star"])
    cleared = cleared.sort_values(["PlayerID", "stage", "t_end"], kind="mergesort")
    first_clears = cleared.groupby(["PlayerID", "stage"]).first()["first_star"].reset_index()
    first_clears.rename(columns={"first_star": "first_clear_star"}, inplace=True)
    return first_clears
