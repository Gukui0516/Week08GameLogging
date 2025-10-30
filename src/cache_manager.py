from __future__ import annotations
from pathlib import Path
import pandas as pd
from .parser import load_csv, filename_to_player_id
from .segment_builder import build_segments as build_stage_segments

class CacheManager:
    def __init__(self, data_dir: str, file_pattern: str = "*.csv",
                 assume_orphan_grab_counts_as_one: bool = True):
        self.data_dir = Path(data_dir)
        self.pattern = file_pattern
        self.assume_orphan = assume_orphan_grab_counts_as_one
        self._file_mtime: dict[Path, float] = {}
        self.raw_by_player: dict[str, pd.DataFrame] = {}
        self.seg_by_player: dict[str, pd.DataFrame] = {}

    def _scan_files(self) -> list[Path]:
        return list(self.data_dir.glob(self.pattern))

    def initial_load(self):
        for p in self._scan_files():
            self._maybe_load(p)

    def _maybe_load(self, path: Path):
        try:
            mtime = path.stat().st_mtime
        except FileNotFoundError:
            return
        prev = self._file_mtime.get(path)
        if prev is None or mtime > prev:
            df = load_csv(path)
            pid = filename_to_player_id(path)
            df["PlayerID"] = pid  # 안전 주입
            self.raw_by_player[pid] = df
            seg = build_stage_segments(df, assume_orphan_grab_counts_as_one=self.assume_orphan)
            self.seg_by_player[pid] = seg
            self._file_mtime[path] = mtime

    def refresh(self):
        current = set(self._scan_files())
        known = set(self._file_mtime.keys())
        for p in current:
            self._maybe_load(p)
        for p in list(known - current):
            pid = filename_to_player_id(p)
            self._file_mtime.pop(p, None)
            self.raw_by_player.pop(pid, None)
            self.seg_by_player.pop(pid, None)

    def all_segments(self) -> pd.DataFrame:
        if not self.seg_by_player:
            return pd.DataFrame(columns=[
                "PlayerID","stage","t_begin","t_end","cleared",
                "clear_time","total_time","retry_cnt","exit_cnt",
                "first_star","final_star",
                "cam_move_cnt","cam_rotate_cnt","cam_pan_cnt","cam_total_cnt",
                "grab_pair_cnt","pushpull_cnt","first_grab_object",
            ])
        return pd.concat(self.seg_by_player.values(), ignore_index=True)

    def all_raw(self) -> pd.DataFrame:
        if not self.raw_by_player:
            return pd.DataFrame(columns=["timestamp","event","level","key","value","PlayerID"])
        return pd.concat(self.raw_by_player.values(), ignore_index=True)

    def players(self) -> list[str]:
        return sorted(self.raw_by_player.keys())
