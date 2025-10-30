# dashboard.py 수정 버전

import pandas as pd
import streamlit as st
import altair as alt
from datetime import datetime
from pathlib import Path
import sys, re, json

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.cache_manager import CacheManager
from src.aggregator import (
    global_stage_means,
    earliest_3_distinct_grabs_for_stage_with_policy,
    global_stage_exit_counts,
    personal_stage_exit_counts,
    personal_first_clear_stars,   # ★ 추가
)

st.set_page_config(page_title="Game Log Analyzer", layout="wide")

# =============== 캐싱 최적화 ===============

@st.cache_resource
def get_cache_manager(config_path: str, data_root: str) -> CacheManager:
    cfg_file = Path(config_path)
    if cfg_file.exists():
        cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
    else:
        cfg = {"data_dir": "./DATA", "file_pattern": "*.csv", 
               "assume_orphan_grab_counts_as_one": True}
    cm = CacheManager(data_root, cfg.get("file_pattern", "*.csv"),
                      cfg.get("assume_orphan_grab_counts_as_one", True))
    cm.initial_load()
    return cm

@st.cache_data(ttl=60)
def get_date_dirs(base_path: str) -> list[str]:
    base = Path(base_path)
    if not base.exists():
        return []
    return [p.name for p in sorted([d for d in base.iterdir() 
            if d.is_dir() and re.fullmatch(r"\d{4}-\d{2}-\d{2}", d.name)])]

@st.cache_data(ttl=30)
def load_all_data(_cm: CacheManager) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    segs_all = _cm.all_segments()
    raw_all = _cm.all_raw()
    players = _cm.players()
    return segs_all, raw_all, players

@st.cache_data
def compute_global_stats(segs_sel: pd.DataFrame, selected_players: list[str]) -> pd.DataFrame:
    gmean = global_stage_means(segs_sel)
    gexit = global_stage_exit_counts(segs_sel, selected_players)
    return gmean.merge(gexit, on="stage", how="left")

@st.cache_data
def compute_personal_exits(segs_sel: pd.DataFrame, selected_players: list[str]) -> pd.DataFrame:
    return personal_stage_exit_counts(segs_sel, selected_players)

@st.cache_data
def compute_personal_first_clear(segs_sel: pd.DataFrame, selected_players: list[str]) -> pd.DataFrame:
    return personal_first_clear_stars(segs_sel, selected_players)

@st.cache_data
def compute_first_grabs(raw_all: pd.DataFrame, stage: str, 
                        selected_players: list[str], policy: str) -> pd.DataFrame:
    return earliest_3_distinct_grabs_for_stage_with_policy(
        raw_all, stage=stage, selected_players=selected_players,
        policy=policy, exclude_roots=True
    )

# =============== 설정 로딩 ===============
cfg_path = str(ROOT / "config.json")
base_cfg = {}
cfg_file = Path(cfg_path)
if cfg_file.exists():
    base_cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
BASE_DATA_DIR = Path(base_cfg.get("data_dir", "./DATA")).resolve()

# =============== 사이드바: 날짜 폴더 선택 ===============
st.sidebar.header("데이터 소스")
date_dirs = get_date_dirs(str(BASE_DATA_DIR))
today_str = datetime.now().strftime("%Y-%m-%d")
if not date_dirs:
    (BASE_DATA_DIR / today_str).mkdir(parents=True, exist_ok=True)
    date_dirs = [today_str]

selected_date = st.sidebar.selectbox(
    "날짜 선택 (yyyy-mm-dd)", 
    options=date_dirs, 
    index=len(date_dirs)-1
)
date_root = (BASE_DATA_DIR / selected_date)
date_root.mkdir(parents=True, exist_ok=True)

if st.sidebar.button("🔄 Refresh"):
    st.cache_data.clear()
    cm = get_cache_manager(cfg_path, str(date_root))
    cm.refresh()
    st.rerun()

# =============== 데이터 적재 ===============
cm = get_cache_manager(cfg_path, str(date_root))
segs_all, raw_all, all_players = load_all_data(cm)

selected_players = st.sidebar.multiselect(
    "플레이어 선택", 
    all_players, 
    default=all_players, 
    key="players"
)
st.sidebar.write(f"선택 {len(selected_players)} / 전체 {len(all_players)}")

segs_sel = (segs_all[segs_all["PlayerID"].isin(selected_players)] 
            if selected_players else segs_all.iloc[0:0])

# KPI
k1, k2 = st.columns([1,3])
with k1:
    st.metric("선택된 플레이어 수", len(selected_players))
with k2:
    st.caption(f"데이터 폴더: {date_root}")

# =============== 라벨/설명 ===============
metric_labels = {
    "mean_stage_play_time": "스테이지 플레이타임(초)",
    "mean_clear_time": "클리어타임(초)",
    "mean_first_clear_star": "첫 클리어 별(평균)",
    "mean_retry": "리트라이 횟수",
    "exit_sum": "포기 횟수(합계)",
    "mean_cam_total": "카메라 조작(통합)",
    "mean_cam_move": "카메라 이동",
    "mean_cam_rotate": "카메라 회전",
    "mean_cam_pan": "카메라 패닝",
    "mean_grab_pair": "그랩(세트)",
    "mean_pushpull": "밀·당 횟수",
}

metric_notes = {
    "mean_stage_play_time": "StageBegin ~ StageClear 시간(클리어된 시도만 평균).",
    "mean_clear_time": "마지막 StageRetry(있다면) ~ StageClear 시간(클리어된 시도만 평균).",
    "mean_first_clear_star": "플레이어×스테이지 단위로 '첫 클리어' 시 받은 별을 뽑아 스테이지별 평균.",
    "mean_retry": "시도 내 StageRetry 발생 횟수 평균.",
    "exit_sum": "선택된 플레이어의 StageExit 시도 개수 합.",
    "mean_cam_total": "줌/회전/패닝 이벤트 합의 평균.",
    "mean_cam_move": "CameraZoom 횟수 평균.",
    "mean_cam_rotate": "CameraRotate 횟수 평균.",
    "mean_cam_pan": "CameraPanning 횟수 평균.",
    "mean_grab_pair": "InputGrab~InputGrabBreak 한 쌍을 1회로 본 횟수 평균.",
    "mean_pushpull": "InputPushPull 횟수 평균.",
}

def render_metric_help_inline(selected_key: str):
    note = metric_notes.get(selected_key)
    if note:
        st.caption(f"**계산식** — {metric_labels[selected_key]}: {note}")

def render_metric_help_full():
    with st.expander("지표 계산 규칙 보기", expanded=False):
        st.markdown("\n".join([f"- **{metric_labels[k]}**: {metric_notes[k]}" 
                               for k in metric_labels if k in metric_notes]))
        st.markdown("> **공통**: 평균은 해당 지표가 정의된 시도만 분모로 계산합니다.")

# =============== 전역 지표 ===============
st.subheader("전체 지표(선택된 플레이어 기준)")

if segs_sel.empty:
    st.info("표본이 없습니다. 선택한 날짜 폴더에 CSV를 넣고 Refresh 하세요.")
else:
    gstats = compute_global_stats(segs_sel, selected_players)
    picked = st.selectbox(
        "지표 선택", 
        list(metric_labels.keys()), 
        format_func=lambda k: metric_labels[k], 
        key="global_metric"
    )
    chart_df = gstats[["stage", picked]].dropna()
    chart = (
        alt.Chart(chart_df)
        .mark_bar()
        .encode(
            x=alt.X("stage:N", sort=None, axis=alt.Axis(labelAngle=0, title="스테이지")),
            y=alt.Y(f"{picked}:Q", title=metric_labels[picked]),
            color=alt.Color("stage:N", legend=None),
            tooltip=[alt.Tooltip("stage:N", title="스테이지"),
                     alt.Tooltip(f"{picked}:Q", title=metric_labels[picked])]
        )
        .properties(height=320)
    )
    st.altair_chart(chart, use_container_width=True)
    render_metric_help_inline(picked)

    kmap = {
        "stage": "스테이지",
        "n_players_used": "사용된 플레이어 수",
        "mean_stage_play_time": "스테이지 플레이타임(초)",
        "mean_clear_time": "클리어타임(초)",
        "mean_first_clear_star": "첫 클리어 별(평균)",
        "mean_retry": "리트라이 횟수",
        "exit_sum": "포기 횟수(합계)",
        "mean_cam_move": "카메라 이동",
        "mean_cam_rotate": "카메라 회전",
        "mean_cam_pan": "카메라 패닝",
        "mean_cam_total": "카메라 조작(통합)",
        "mean_grab_pair": "그랩(세트)",
        "mean_pushpull": "밀·당 횟수",
    }
    st.dataframe(gstats.rename(columns=kmap), use_container_width=True)
    render_metric_help_full()

# =============== 스테이지별 첫 그랩 TOP3 ===============
st.subheader("스테이지별 가장 먼저 집은 오브젝트")
stages_fg = sorted(segs_sel["stage"].dropna().unique().tolist())

if not stages_fg:
    st.info("선택 가능한 스테이지가 없습니다.")
else:
    stage_fg = st.selectbox("Stage 선택(필수)", options=stages_fg, key="stage_fast3_policy")
    tabs = st.tabs(["가장 처음", "가장 최신", "최단 클리어"])

    def _render_table(policy_key: str, tab_label: str):
        df3 = compute_first_grabs(
            raw_all, stage_fg, 
            tuple(selected_players) if selected_players else None,
            policy_key
        )
        if df3.empty:
            st.info(f"{tab_label}: 데이터가 없습니다.")
            return
        labels = [f"가장 먼저 집은 물체{r}" for r in df3["rank"]]
        view = df3.copy()
        view.insert(0, "라벨", labels)
        view.rename(columns={
            "object_name": "오브젝트",
            "timestamp": "시각",
            "dt_from_begin": "경과(초)",
            "PlayerID": "플레이어"
        }, inplace=True)
        st.table(view[["라벨","오브젝트","시각","경과(초)","플레이어"]])

    with tabs[0]:
        _render_table("earliest", "가장 처음(가장 먼저 끝난 시도)")
    with tabs[1]:
        _render_table("latest", "가장 최신(가장 나중에 끝난 시도)")
    with tabs[2]:
        _render_table("shortest_clear", "최단 클리어(클리어 없으면 최신 대체)")

# =============== 개인 지표 ===============
st.subheader("개인 지표")

def dedup_segments(df: pd.DataFrame, policy: str) -> pd.DataFrame:
    if df.empty:
        return df
    d = df.copy().sort_values(["stage","t_begin","t_end"], kind="mergesort")
    if policy == "전체 시도(그대로)":
        return d
    elif policy == "최신 시도":
        idx = d.groupby("stage")["t_end"].idxmax()
        return d.loc[idx].sort_values("stage")
    elif policy == "최고 기록(최단 클리어)":
        cleared = d[(d["cleared"] == True) & d["clear_time"].notna()].copy()
        if not cleared.empty:
            idx = cleared.groupby("stage")["clear_time"].idxmin()
            return cleared.loc[idx].sort_values("stage")
        else:
            idx = d.groupby("stage")["t_end"].idxmax()
            return d.loc[idx].sort_values("stage")
    elif policy == "첫 시도":
        idx = d.groupby("stage")["t_begin"].idxmin()
        return d.loc[idx].sort_values("stage")
    else:
        return d

if not selected_players:
    st.info("좌측에서 플레이어를 선택하세요.")
else:
    tabs = st.tabs(selected_players)
    pexit_all  = compute_personal_exits(segs_sel, tuple(selected_players))
    pfirst_all = compute_personal_first_clear(segs_sel, tuple(selected_players))  # ★ 추가

    for tab, pid in zip(tabs, selected_players):
        with tab:
            st.markdown(f"**Player:** `{pid}`")
            pseg = segs_sel[segs_sel["PlayerID"] == pid].copy()
            if pseg.empty:
                st.info("데이터 없음")
                continue

            options = ["전체 시도(그대로)", "최신 시도", "최고 기록(최단 클리어)", "첫 시도"]
            default_index = options.index("최고 기록(최단 클리어)")
            policy = st.selectbox(
                "스테이지 중복 시도 처리",
                options,
                index=default_index,  # ← 기본값: 최고 기록(최단 클리어)
                key=f"dedup_{pid}"
            )
            pview = dedup_segments(pseg, policy)

            base = pview[[
                "stage","stage_play_time","clear_time",
                "retry_cnt",
                "grab_pair_cnt","pushpull_cnt",
                "cam_move_cnt","cam_rotate_cnt","cam_pan_cnt","cam_total_cnt"
            ]].copy()

            # 개인: 포기 합계 + 첫 클리어 별
            pexit  = pexit_all[pexit_all["PlayerID"] == pid][["stage","exit_sum"]]
            pfirst = pfirst_all[pfirst_all["PlayerID"] == pid][["stage","first_clear_star"]]

            disp = base.merge(pexit, on="stage", how="left").merge(pfirst, on="stage", how="left")
            disp = disp.fillna({"exit_sum": 0})

            # 포맷팅
            for c in ["stage_play_time", "clear_time"]:
                if c in disp:
                    disp[c] = pd.to_numeric(disp[c], errors="coerce").round(3)
            if "first_clear_star" in disp:
                disp["first_clear_star"] = pd.to_numeric(disp["first_clear_star"], errors="coerce").astype("Int64")
            for c in ["retry_cnt","exit_sum","grab_pair_cnt","pushpull_cnt",
                      "cam_move_cnt","cam_rotate_cnt","cam_pan_cnt","cam_total_cnt"]:
                if c in disp:
                    disp[c] = pd.to_numeric(disp[c], errors="coerce").fillna(0).astype("Int64")

            kmap_personal = {
                "stage": "스테이지",
                "stage_play_time": "스테이지 플레이타임(초)",
                "clear_time": "클리어타임(초)",
                "first_clear_star": "첫 클리어 별",   # ★ 추가
                "retry_cnt": "리트라이",
                "exit_sum": "포기 횟수(합계)",
                "grab_pair_cnt": "그랩(세트)",
                "pushpull_cnt": "밀·당",
                "cam_move_cnt": "카메라 이동",
                "cam_rotate_cnt": "카메라 회전",
                "cam_pan_cnt": "카메라 패닝",
                "cam_total_cnt": "카메라 조작(통합)",
            }
            disp_korean = disp.rename(columns=kmap_personal)
            st.dataframe(disp_korean, use_container_width=True)

            # 개인 보조 그래프(예: 플레이타임)
            if "스테이지" in disp_korean.columns and "스테이지 플레이타임(초)" in disp_korean.columns:
                cdf = disp_korean[["스테이지","스테이지 플레이타임(초)"]].rename(
                    columns={"스테이지":"stage","스테이지 플레이타임(초)":"play_time"}
                ).dropna()
                if not cdf.empty:
                    chart_p = (
                        alt.Chart(cdf)
                        .mark_bar()
                        .encode(
                            x=alt.X("stage:N", axis=alt.Axis(labelAngle=0, title="스테이지")),
                            y=alt.Y("play_time:Q", title="스테이지 플레이타임(초)"),
                            color=alt.Color("stage:N", legend=None),
                            tooltip=[alt.Tooltip("stage:N", title="스테이지"),
                                     alt.Tooltip("play_time:Q", title="스테이지 플레이타임(초)")]
                        )
                        .properties(height=260)
                    )
                    st.altair_chart(chart_p, use_container_width=True)
