#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dialogue Edit Seam Smoother core engine.

목표:
- 대사 편집점의 '뚝 끊김', '틱', 접합 이질감을 부드럽게 완화
- 클릭 제거기보다 seam smoothing 관점으로 설계
- marker 기반 반자동 처리 우선, auto scan은 보조

의존성:
    pip install numpy scipy soundfile
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfiltfilt


@dataclass
class RepairConfig:
    auto_detect: bool = True
    marker_window_ms: float = 30.0
    analysis_window_ms: float = 8.0
    pre_context_ms: float = 10.0
    post_context_ms: float = 10.0
    micro_fade_ms: float = 1.0
    crossfade_ms: float = 4.0
    sensitivity: float = 1.0
    seam_threshold: float = 0.55
    protect_transients: bool = True
    transient_protect_strength: float = 0.8
    min_separation_ms: float = 8.0


@dataclass
class SeamEvent:
    sample_index: int
    time_sec: float
    rms_jump: float
    corr_loss: float
    dc_jump: float
    spectral_mismatch: float
    transient_score: float
    seam_score: float
    decision: str


def ms_to_samples(ms: float, sr: int) -> int:
    return max(1, int(round(ms * sr / 1000.0)))


def safe_mono(x: np.ndarray) -> np.ndarray:
    if x.ndim == 1:
        return x.astype(np.float64, copy=False)
    return np.mean(x, axis=1, dtype=np.float64)


# keep old API name for app compatibility if needed
ensure_mono = safe_mono


def read_markers(path: Optional[str]) -> List[float]:
    if not path:
        return []
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Marker file not found: {p}")
    out: List[float] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        # allow csv row with first field as seconds
        first = line.split(",", 1)[0].strip()
        out.append(float(first))
    return out


def merge_close_indices(indices: np.ndarray, min_gap: int) -> np.ndarray:
    if len(indices) == 0:
        return indices.astype(np.int64)
    indices = np.sort(indices)
    merged = [int(indices[0])]
    for idx in indices[1:]:
        if idx - merged[-1] >= min_gap:
            merged.append(int(idx))
    return np.asarray(merged, dtype=np.int64)


def moving_rms(x: np.ndarray, win: int) -> np.ndarray:
    win = max(1, int(win))
    pad = win // 2
    xp = np.pad(x * x, (pad, pad), mode="reflect")
    kernel = np.ones(win, dtype=np.float64) / win
    y = np.convolve(xp, kernel, mode="valid")
    return np.sqrt(np.maximum(y, 1e-12))


def robust_z(x: np.ndarray) -> np.ndarray:
    med = np.median(x)
    mad = np.median(np.abs(x - med)) + 1e-12
    return 0.6745 * (x - med) / mad


def bandpass(x: np.ndarray, sr: int, low: float, high: float, order: int = 4) -> np.ndarray:
    nyq = sr * 0.5
    low_n = max(low / nyq, 1e-5)
    high_n = min(high / nyq, 0.999)
    if high_n <= low_n:
        return x.copy()
    sos = butter(order, [low_n, high_n], btype="bandpass", output="sos")
    return sosfiltfilt(sos, x)


def short_spectrum(seg: np.ndarray, n_fft: int) -> np.ndarray:
    if len(seg) < n_fft:
        seg = np.pad(seg, (0, n_fft - len(seg)))
    win = np.hanning(n_fft)
    spec = np.fft.rfft(seg[:n_fft] * win)
    mag = np.abs(spec)
    return mag / (np.sum(mag) + 1e-12)


def compute_transient_score(x: np.ndarray, sr: int, center: int) -> float:
    w = ms_to_samples(15.0, sr)
    a = max(0, center - w)
    b = min(len(x), center + w)
    seg = x[a:b]
    if len(seg) < 32:
        return 0.0
    env = moving_rms(seg, ms_to_samples(0.5, sr))
    c = np.clip(center - a, 1, len(env) - 2)
    pre = float(np.mean(env[max(0, c - ms_to_samples(3.0, sr)):c]) + 1e-12)
    post = float(np.mean(env[c:min(len(env), c + ms_to_samples(8.0, sr))]) + 1e-12)
    ratio = post / pre
    return float(np.clip((ratio - 1.2) / 4.0, 0.0, 1.0))


def evaluate_one_seam(x: np.ndarray, sr: int, center: int, cfg: RepairConfig) -> SeamEvent:
    pre = ms_to_samples(cfg.pre_context_ms, sr)
    post = ms_to_samples(cfg.post_context_ms, sr)
    a0 = max(0, center - pre)
    a1 = max(0, center)
    b0 = min(len(x), center)
    b1 = min(len(x), center + post)
    left = x[a0:a1]
    right = x[b0:b1]
    m = min(len(left), len(right))
    if m < 16:
        return SeamEvent(center, center / sr, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "skip")
    left = left[-m:]
    right = right[:m]

    left_rms = float(np.sqrt(np.mean(left * left)) + 1e-12)
    right_rms = float(np.sqrt(np.mean(right * right)) + 1e-12)
    rms_jump = abs(np.log10(right_rms / left_rms)) * 2.0

    denom = (np.linalg.norm(left) * np.linalg.norm(right)) + 1e-12
    corr = float(np.dot(left, right) / denom)
    corr_loss = 1.0 - np.clip((corr + 1.0) * 0.5, 0.0, 1.0)

    dc_jump = abs(float(x[min(len(x) - 1, center)] - x[max(0, center - 1)]))
    dc_jump = float(np.clip(dc_jump * 5.0, 0.0, 1.0))

    n_fft = 1
    while n_fft < m:
        n_fft *= 2
    n_fft = max(64, min(n_fft, 1024))
    lspec = short_spectrum(left, n_fft)
    rspec = short_spectrum(right, n_fft)
    spectral_mismatch = float(np.clip(np.mean(np.abs(lspec - rspec)) * 10.0, 0.0, 1.0))

    transient_score = compute_transient_score(x, sr, center) if cfg.protect_transients else 0.0

    seam_score = (
        0.28 * np.clip(rms_jump, 0.0, 1.0)
        + 0.28 * np.clip(corr_loss, 0.0, 1.0)
        + 0.20 * np.clip(dc_jump, 0.0, 1.0)
        + 0.24 * np.clip(spectral_mismatch, 0.0, 1.0)
    )
    seam_score *= cfg.sensitivity
    seam_score *= (1.0 - transient_score * 0.45 * cfg.transient_protect_strength)
    seam_score = float(np.clip(seam_score, 0.0, 1.5))

    decision = "repair" if seam_score >= cfg.seam_threshold else "skip"
    return SeamEvent(
        sample_index=center,
        time_sec=center / sr,
        rms_jump=float(np.clip(rms_jump, 0.0, 1.0)),
        corr_loss=float(np.clip(corr_loss, 0.0, 1.0)),
        dc_jump=dc_jump,
        spectral_mismatch=spectral_mismatch,
        transient_score=transient_score,
        seam_score=seam_score,
        decision=decision,
    )


def marker_collect_candidates(mono: np.ndarray, sr: int, markers_sec: Sequence[float], cfg: RepairConfig) -> np.ndarray:
    if not markers_sec:
        return np.asarray([], dtype=np.int64)
    search = ms_to_samples(cfg.marker_window_ms, sr)
    d = np.abs(np.diff(mono, prepend=mono[0]))
    hf = moving_rms(bandpass(mono, sr, 2000.0, min(sr * 0.45, 12000.0)), ms_to_samples(0.6, sr))
    out: List[int] = []
    for t in markers_sec:
        c = int(round(t * sr))
        a = max(0, c - search)
        b = min(len(mono), c + search)
        if b - a < 8:
            continue
        combo = robust_z(d[a:b]) + robust_z(hf[a:b])
        best = a + int(np.argmax(combo))
        out.append(best)
    return merge_close_indices(np.asarray(out, dtype=np.int64), ms_to_samples(cfg.min_separation_ms, sr))


def auto_collect_candidates(mono: np.ndarray, sr: int, cfg: RepairConfig) -> np.ndarray:
    # broad seam scan: find abrupt RMS / spectral flux / diff changes
    env = moving_rms(mono, ms_to_samples(cfg.analysis_window_ms, sr))
    env_diff = np.abs(np.diff(env, prepend=env[0]))
    d = np.abs(np.diff(mono, prepend=mono[0]))
    hf = moving_rms(bandpass(mono, sr, 2000.0, min(sr * 0.45, 12000.0)), ms_to_samples(0.8, sr))
    score = np.clip(robust_z(env_diff), 0.0, None) + 0.6 * np.clip(robust_z(d), 0.0, None) + 0.4 * np.clip(robust_z(hf), 0.0, None)
    hits = np.where(score > (3.8 / max(cfg.sensitivity, 0.1)))[0]
    return merge_close_indices(hits.astype(np.int64), ms_to_samples(cfg.min_separation_ms, sr))


def evaluate_candidates(mono: np.ndarray, sr: int, candidates: np.ndarray, cfg: RepairConfig) -> List[SeamEvent]:
    return [evaluate_one_seam(mono, sr, int(c), cfg) for c in candidates]


def smooth_region(channel: np.ndarray, center: int, sr: int, cfg: RepairConfig) -> np.ndarray:
    y = channel.copy().astype(np.float64)
    fade = ms_to_samples(cfg.micro_fade_ms, sr)
    cf = ms_to_samples(cfg.crossfade_ms, sr)
    a = max(1, center - cf)
    b = min(len(y) - 2, center + cf)
    if b <= a + 1:
        return y

    left = y[a:center]
    right = y[center:b]
    m = min(len(left), len(right))
    if m < 4:
        return y
    left = left[-m:]
    right = right[:m]
    t = np.linspace(0.0, 1.0, m, dtype=np.float64)
    xfade = left * (1.0 - t) + right * t
    y[center - m:center] = xfade
    y[center:center + m] = xfade

    # micro fade around the seam to soften residual edge
    fa = max(0, center - fade)
    fb = min(len(y), center + fade)
    seg = y[fa:fb].copy()
    if len(seg) >= 4:
        half = len(seg) // 2
        fade_out = np.linspace(1.0, 0.7, half, dtype=np.float64)
        fade_in = np.linspace(0.7, 1.0, len(seg) - half, dtype=np.float64)
        env = np.concatenate([fade_out, fade_in])
        y[fa:fb] = seg * env
    return y


def apply_repairs(audio: np.ndarray, sr: int, events: Sequence[SeamEvent], cfg: RepairConfig) -> np.ndarray:
    repair_events = [ev for ev in events if getattr(ev, "decision", "") == "repair"]
    out = audio.copy().astype(np.float64)
    for ev in repair_events:
        c = int(ev.sample_index)
        if out.ndim == 1:
            out = smooth_region(out, c, sr, cfg)
        else:
            for ch in range(out.shape[1]):
                out[:, ch] = smooth_region(out[:, ch], c, sr, cfg)
    return out


def write_report(path: str, events: Sequence[SeamEvent]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(asdict(events[0]).keys()) if events else [
        "sample_index", "time_sec", "rms_jump", "corr_loss", "dc_jump", "spectral_mismatch",
        "transient_score", "seam_score", "decision"
    ]
    with p.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for ev in events:
            writer.writerow(asdict(ev))


def process_file(
    input_path: str,
    output_path: str,
    report_path: Optional[str],
    markers_path: Optional[str],
    cfg: RepairConfig,
) -> Tuple[np.ndarray, int, List[SeamEvent]]:
    audio, sr = sf.read(input_path, always_2d=False)
    mono = safe_mono(audio)
    markers_sec = read_markers(markers_path)
    candidate_sets = []
    if markers_sec:
        candidate_sets.append(marker_collect_candidates(mono, sr, markers_sec, cfg))
    if cfg.auto_detect or not markers_sec:
        candidate_sets.append(auto_collect_candidates(mono, sr, cfg))
    candidates = np.unique(np.concatenate(candidate_sets)) if candidate_sets else np.asarray([], dtype=np.int64)
    candidates = merge_close_indices(candidates, ms_to_samples(cfg.min_separation_ms, sr))
    events = evaluate_candidates(mono, sr, candidates, cfg)
    repaired = apply_repairs(audio, sr, events, cfg)
    sf.write(output_path, repaired, sr)
    if report_path:
        write_report(report_path, events)
    return repaired, sr, events


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Dialogue Edit Seam Smoother")
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--report", default="")
    p.add_argument("--markers", default="")
    p.add_argument("--no-auto-detect", action="store_true")
    p.add_argument("--sensitivity", type=float, default=1.0)
    p.add_argument("--crossfade-ms", type=float, default=4.0)
    p.add_argument("--micro-fade-ms", type=float, default=1.0)
    p.add_argument("--threshold", type=float, default=0.55)
    return p


def main() -> None:
    args = build_argparser().parse_args()
    cfg = RepairConfig(
        auto_detect=not args.no_auto_detect,
        sensitivity=max(0.1, float(args.sensitivity)),
        crossfade_ms=max(0.5, float(args.crossfade_ms)),
        micro_fade_ms=max(0.2, float(args.micro_fade_ms)),
        seam_threshold=max(0.1, float(args.threshold)),
    )
    _, sr, events = process_file(
        input_path=args.input,
        output_path=args.output,
        report_path=args.report or None,
        markers_path=args.markers or None,
        cfg=cfg,
    )
    repaired_count = sum(1 for e in events if e.decision == "repair")
    print("=" * 60)
    print("Dialogue Edit Seam Smoother complete")
    print(f"Sample Rate   : {sr} Hz")
    print(f"Candidates    : {len(events)}")
    print(f"Repaired      : {repaired_count}")
    print("=" * 60)


if __name__ == "__main__":
    main()
