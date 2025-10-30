# app_cli.py
"""
Usage:
  python app_cli.py --data ./DATA --players all
  python app_cli.py --data ./DATA --players player1,player2
Outputs CSVs to ./outputs/
"""
import argparse
from pathlib import Path
import pandas as pd
from src.cache_manager import CacheManager
from src.aggregator import (
    global_stage_means,
    personal_stage_exit_counts,
    earliest_3_distinct_grabs_for_stage_with_policy,
)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="./DATA")
    ap.add_argument("--players", default="all")
    ap.add_argument("--out", default="./outputs")
    args = ap.parse_args()

    cm = CacheManager(args.data)
    cm.initial_load()
    players = cm.players() if args.players == "all" else args.players.split(",")

    segs = cm.all_segments()
    segs_sel = segs[segs["PlayerID"].isin(players)] if players else segs.iloc[0:0]

    outdir = Path(args.out); outdir.mkdir(parents=True, exist_ok=True)

    # 전역 평균
    global_df = global_stage_means(segs_sel)
    global_df.to_csv(outdir/"global_stage_means.csv", index=False, encoding="utf-8")

    # 개인: 포기 합계
    personal_exit = personal_stage_exit_counts(segs_sel, players)
    personal_exit.to_csv(outdir/"personal_exit_counts.csv", index=False, encoding="utf-8")

    # 스테이지별 First-Grab TOP3 (정책: earliest)
    raw_all = cm.all_raw()
    rows = []
    for stg in sorted(segs_sel["stage"].dropna().unique().tolist()):
        top3 = earliest_3_distinct_grabs_for_stage_with_policy(
            raw_all, stage=stg, selected_players=players, policy="earliest", exclude_roots=True
        )
        if not top3.empty:
            top3["stage"] = stg
            rows.append(top3)
    top_all = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=["rank","object_name","timestamp","dt_from_begin","PlayerID","stage"])
    top_all.to_csv(outdir/"first_grab_top3_by_stage.csv", index=False, encoding="utf-8")

    print(f"Saved to {outdir}")

if __name__ == "__main__":
    main()
