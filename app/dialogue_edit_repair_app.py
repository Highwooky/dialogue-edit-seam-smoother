#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dialogue Edit Seam Smoother GUI.

주요 기능:
- 대사 편집점 seam 분석 / smoothing
- drag & drop
- 진행률 + 경과시간 + 예상 남은 시간
- 한국어 / English
- Easy Seam 노브
- 선택 seam만 복원 저장
- 취소 버튼
- 선택 seam 원본/복원 A/B 미리듣기 (macOS afplay)
- assets/icon.png 자동 창 아이콘 적용
- soundfile / libsndfile 지연 로딩
"""

from __future__ import annotations

import argparse
import csv
import importlib
import os
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QBrush, QDragEnterEvent, QDropEvent, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDial,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

APP_TITLE = "Dialogue Edit Seam Smoother"
DEV_FOOTER = "JTBC Mediatech • Production J Division • Post Production Team • Yu Byungwook"
ASSETS_DIR = Path(__file__).resolve().parent / "assets"
ICON_PATH = ASSETS_DIR / "icon.png"

LANG_TEXTS: Dict[str, Dict[str, str]] = {
    "en": {
        "subtitle": "Smooth abrupt dialogue edit seams with short fades and crossfades",
        "files": "Files",
        "input": "Input",
        "markers": "Markers",
        "output": "Output",
        "open_wav": "Open WAV",
        "open_markers": "Open Markers",
        "set_output": "Set Output",
        "auto_output_ph": "Auto-generate or set manually",
        "options": "Options",
        "easy_mode": "Easy Seam",
        "easy_hint": "One knob links sensitivity, crossfade width and threshold",
        "crossfade_ms": "Crossfade (ms)",
        "micro_fade_ms": "Micro fade (ms)",
        "threshold": "Seam threshold",
        "preview_ms": "Preview length (ms)",
        "auto_detect": "Enable auto scan",
        "transient_protect": "Protect transients",
        "language": "Language",
        "run": "Run",
        "analyze": "Analyze",
        "repair_save": "Smooth All + Save",
        "repair_selected": "Smooth Selected + Save",
        "save_report": "Save Report CSV",
        "cancel": "Cancel",
        "preview_original": "Play Original",
        "preview_smoothed": "Play Smoothed",
        "stop_preview": "Stop Preview",
        "log": "Log",
        "waveform": "Waveform",
        "detected_events": "Detected Seams",
        "status": "Status",
        "idle": "Idle",
        "ready_backend": "[READY] audio backend loaded",
        "warn_backend": "[WARN] audio backend unavailable",
        "audio_backend": "Audio Backend",
        "audio_backend_ok": "soundfile / dialogue_edit_repair_mvp backend is available.",
        "audio_backend_unavailable": "Audio Backend Unavailable",
        "file_menu": "File",
        "tools_menu": "Tools",
        "help_menu": "Help",
        "quit": "Quit",
        "about": "About",
        "check_backend": "Check Audio Backend",
        "loaded_audio": "Loaded audio",
        "sample_rate": "Sample rate",
        "channels": "Channels",
        "loaded_markers": "Loaded markers",
        "analyze_failed": "Analyze Failed",
        "repair_failed": "Repair Failed",
        "export_failed": "Export Failed",
        "open_audio_failed": "Open Audio Failed",
        "need_open_wav": "Open a WAV/AIFF file first.",
        "need_analyze_first": "Run Analyze first.",
        "need_output_path": "Choose an output path.",
        "need_select_event": "Select one or more seam events first.",
        "analyze_complete": "Analyze Complete",
        "repair_complete": "Repair Complete",
        "export_complete": "Export Complete",
        "saved": "Saved",
        "saved_report": "Saved report",
        "applied_repairs": "Applied smoothing count",
        "detected_events_msg": "Detected seams",
        "drag_hint": "Drag and drop WAV / AIFF / TXT / CSV files onto this window.",
        "status_analyzing": "Analyzing...",
        "status_repairing": "Smoothing and saving...",
        "status_previewing": "Previewing...",
        "status_cancelled": "Cancelled",
        "status_done": "Done",
        "status_error": "Error",
        "elapsed": "Elapsed",
        "remaining": "Remaining",
        "progress_candidates": "Candidates",
        "progress_events": "Events",
        "selection_count": "Selected seams",
        "time": "Time",
        "score": "Seam",
        "rms_jump": "RMS",
        "corr_loss": "Corr",
        "spec": "Spec",
        "decision": "Decision",
        "drop_rejected": "Unsupported dropped file.",
        "preview_not_available": "Preview command is not available on this system.",
        "preview_started": "Preview started",
        "preview_stopped": "Preview stopped",
        "about_body": (
            "Dialogue Edit Seam Smoother\n\n"
            "Purpose:\n"
            "Reduce abrupt dialogue edit seams with short fades and crossfades while protecting natural transients.\n\n"
            "Designed for offline-safe macOS Apple Silicon workflow."
        ),
    },
    "ko": {
        "subtitle": "대사 편집점의 갑작스러운 단절을 짧은 페이드와 크로스페이드로 완화",
        "files": "파일",
        "input": "입력",
        "markers": "마커",
        "output": "출력",
        "open_wav": "WAV 열기",
        "open_markers": "마커 열기",
        "set_output": "출력 설정",
        "auto_output_ph": "자동 생성 또는 직접 지정",
        "options": "옵션",
        "easy_mode": "간편 Seam",
        "easy_hint": "하나의 노브로 민감도, 크로스페이드 폭, 임계값을 함께 조정",
        "crossfade_ms": "크로스페이드 (ms)",
        "micro_fade_ms": "마이크로 페이드 (ms)",
        "threshold": "Seam 임계값",
        "preview_ms": "미리듣기 길이 (ms)",
        "auto_detect": "자동 스캔 사용",
        "transient_protect": "트랜지언트 보호",
        "language": "언어",
        "run": "실행",
        "analyze": "분석",
        "repair_save": "전체 보정 + 저장",
        "repair_selected": "선택 보정 + 저장",
        "save_report": "CSV 리포트 저장",
        "cancel": "취소",
        "preview_original": "원본 재생",
        "preview_smoothed": "보정 재생",
        "stop_preview": "재생 정지",
        "log": "로그",
        "waveform": "파형",
        "detected_events": "탐지 Seam",
        "status": "상태",
        "idle": "대기",
        "ready_backend": "[READY] 오디오 백엔드 로드 완료",
        "warn_backend": "[WARN] 오디오 백엔드를 사용할 수 없음",
        "audio_backend": "오디오 백엔드",
        "audio_backend_ok": "soundfile / dialogue_edit_repair_mvp 백엔드를 사용할 수 있습니다.",
        "audio_backend_unavailable": "오디오 백엔드를 사용할 수 없음",
        "file_menu": "파일",
        "tools_menu": "도구",
        "help_menu": "도움말",
        "quit": "종료",
        "about": "정보",
        "check_backend": "오디오 백엔드 확인",
        "loaded_audio": "오디오 로드",
        "sample_rate": "샘플레이트",
        "channels": "채널 수",
        "loaded_markers": "마커 로드",
        "analyze_failed": "분석 실패",
        "repair_failed": "보정 실패",
        "export_failed": "내보내기 실패",
        "open_audio_failed": "오디오 열기 실패",
        "need_open_wav": "먼저 WAV/AIFF 파일을 열어야 합니다.",
        "need_analyze_first": "먼저 분석을 실행해야 합니다.",
        "need_output_path": "출력 경로를 지정해야 합니다.",
        "need_select_event": "하나 이상의 Seam 이벤트를 먼저 선택해야 합니다.",
        "analyze_complete": "분석 완료",
        "repair_complete": "보정 완료",
        "export_complete": "내보내기 완료",
        "saved": "저장됨",
        "saved_report": "리포트 저장",
        "applied_repairs": "적용된 보정 수",
        "detected_events_msg": "탐지 Seam 수",
        "drag_hint": "이 창으로 WAV / AIFF / TXT / CSV 파일을 드래그 앤 드롭할 수 있습니다.",
        "status_analyzing": "분석 중...",
        "status_repairing": "보정 및 저장 중...",
        "status_previewing": "미리듣기 중...",
        "status_cancelled": "취소됨",
        "status_done": "완료",
        "status_error": "오류",
        "elapsed": "경과",
        "remaining": "예상 남은 시간",
        "progress_candidates": "후보",
        "progress_events": "이벤트",
        "selection_count": "선택 Seam 수",
        "time": "시간",
        "score": "Seam",
        "rms_jump": "RMS",
        "corr_loss": "상관",
        "spec": "스펙트럼",
        "decision": "판정",
        "drop_rejected": "지원하지 않는 드롭 파일입니다.",
        "preview_not_available": "이 시스템에서 미리듣기 명령을 사용할 수 없습니다.",
        "preview_started": "미리듣기 시작",
        "preview_stopped": "미리듣기 정지",
        "about_body": (
            "Dialogue Edit Seam Smoother\n\n"
            "목적:\n"
            "대사 편집점의 갑작스러운 단절을 짧은 페이드와 크로스페이드로 완화하고 자연스러운 트랜지언트를 보호합니다.\n\n"
            "폐쇄망 macOS Apple Silicon 환경을 기준으로 설계되었습니다."
        ),
    },
}

DARK_QSS = """
QWidget { background-color: #0b1220; color: #e5eefc; font-size: 13px; }
QMainWindow { background-color: #0b1220; }
QGroupBox { border: 1px solid #25406e; border-radius: 12px; margin-top: 10px; padding-top: 10px; font-weight: 700; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 6px; color: #7dd3fc; }
QPushButton { background-color: #123056; border: 1px solid #2f5fa8; border-radius: 10px; padding: 8px 12px; font-weight: 700; }
QPushButton:hover { background-color: #18406f; }
QPushButton:pressed { background-color: #0e2744; }
QPushButton:disabled { color: #8fa3c5; background-color: #0f1a2b; }
QLineEdit, QDoubleSpinBox, QTextEdit, QTableWidget, QComboBox { background-color: #0f1a2b; border: 1px solid #27466f; border-radius: 8px; selection-background-color: #2563eb; padding: 4px; }
QHeaderView::section { background-color: #13233b; color: #dbeafe; border: 0; padding: 6px; font-weight: 700; }
QTableWidget { gridline-color: #223655; }
QTableWidget::item:selected { background-color: #1d4ed8; color: #ffffff; }
QCheckBox { spacing: 8px; }
QLabel#titleLabel { font-size: 24px; font-weight: 800; color: #7dd3fc; }
QLabel#subLabel { color: #9fb7d9; }
QLabel#footerLabel { color: #7b8ba7; font-size: 11px; }
QLabel#dropHintLabel { color: #93c5fd; font-size: 12px; }
QProgressBar { border: 1px solid #27466f; border-radius: 8px; text-align: center; background-color: #0f1a2b; min-height: 20px; }
QProgressBar::chunk { background-color: #2563eb; border-radius: 7px; }
"""

BACKEND_IMPORT_ERROR_HELP = (
    "soundfile 또는 libsndfile 백엔드를 불러오지 못했습니다.\n\n"
    "현재 앱은 GUI는 실행되지만 WAV 열기/저장/분석은 사용할 수 없습니다.\n\n"
    "확인 사항:\n"
    "1. Python 패키지 soundfile 설치 여부\n"
    "2. 시스템/번들에 libsndfile 포함 여부\n"
    "3. 폐쇄망 배포 시 libsndfile 동봉 여부\n\n"
    "원본 오류:\n{error}"
)


def format_seconds(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def decimate_waveform(audio: np.ndarray, sr: int, max_points: int = 120000) -> Tuple[np.ndarray, np.ndarray]:
    mono = ensure_mono(audio)
    if mono.size == 0:
        return np.array([], dtype=np.float64), np.array([], dtype=np.float64)
    if mono.size > max_points:
        step = max(1, mono.size // max_points)
        preview = mono[::step]
        times = np.arange(preview.size, dtype=np.float64) * (step / float(sr))
    else:
        preview = mono.astype(np.float64, copy=False)
        times = np.arange(preview.size, dtype=np.float64) / float(sr)
    return times, preview


def ensure_mono(audio: np.ndarray) -> np.ndarray:
    if audio.ndim == 1:
        return audio.astype(np.float64, copy=False)
    if audio.ndim == 2:
        return np.mean(audio, axis=1, dtype=np.float64)
    raise ValueError(f"Unsupported audio ndim: {audio.ndim}")


class LazyBackend:
    def __init__(self) -> None:
        self.sf: Any = None
        self.mvp: Any = None
        self.last_error: Optional[Exception] = None

    def load(self) -> Tuple[bool, str]:
        if self.sf is not None and self.mvp is not None:
            return True, ""
        try:
            self.sf = importlib.import_module("soundfile")
            self.mvp = importlib.import_module("dialogue_edit_repair_mvp")
            self.last_error = None
            return True, ""
        except Exception as exc:
            self.last_error = exc
            return False, BACKEND_IMPORT_ERROR_HELP.format(error=str(exc))


class DroppableLineEdit(QLineEdit):
    files_dropped = pyqtSignal(list)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if paths:
            self.files_dropped.emit(paths)
            event.acceptProposedAction()
        else:
            event.ignore()


class ProgressTimer:
    def __init__(self) -> None:
        self.start_time = time.perf_counter()

    def elapsed(self) -> float:
        return max(0.0, time.perf_counter() - self.start_time)

    def eta(self, done: int, total: int) -> float:
        if done <= 0 or total <= 0 or done >= total:
            return 0.0
        return max(0.0, (self.elapsed() / max(done, 1)) * (total - done))


class CancelableWorker(QThread):
    cancelled = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def is_cancelled(self) -> bool:
        return self._cancelled


class AnalyzeWorker(CancelableWorker):
    progress = pyqtSignal(int, int, str)
    finished_ok = pyqtSignal(list, str)
    failed = pyqtSignal(str)

    def __init__(self, backend: LazyBackend, audio: np.ndarray, sr: int, markers_path: str, cfg: Any, tr_texts: Dict[str, str]):
        super().__init__()
        self.backend = backend
        self.audio = audio
        self.sr = sr
        self.markers_path = markers_path
        self.cfg = cfg
        self.tr_texts = tr_texts

    def _status(self, timer: ProgressTimer, done: int, total: int, extra: str = "") -> str:
        msg = f"{self.tr_texts['elapsed']}: {format_seconds(timer.elapsed())} / {self.tr_texts['remaining']}: {format_seconds(timer.eta(done, total))}"
        if extra:
            msg += f" / {extra}"
        return msg

    def run(self) -> None:
        try:
            ok, message = self.backend.load()
            if not ok:
                raise RuntimeError(message)
            mvp = self.backend.mvp
            mono = mvp.safe_mono(self.audio)
            timer = ProgressTimer()
            candidate_sets = []
            total_steps = 4
            done = 0
            self.progress.emit(done, total_steps, self.tr_texts["status_analyzing"])

            if self.markers_path:
                markers = mvp.read_markers(self.markers_path)
                candidate_sets.append(mvp.marker_collect_candidates(mono, self.sr, markers, self.cfg))
            done += 1
            if self.is_cancelled():
                self.cancelled.emit(); return
            self.progress.emit(done, total_steps, self._status(timer, done, total_steps))

            if self.cfg.auto_detect or not self.markers_path:
                candidate_sets.append(mvp.auto_collect_candidates(mono, self.sr, self.cfg))
            done += 1
            if self.is_cancelled():
                self.cancelled.emit(); return
            self.progress.emit(done, total_steps, self._status(timer, done, total_steps))

            if candidate_sets:
                candidates = np.unique(np.concatenate(candidate_sets))
                candidates = mvp.merge_close_indices(candidates, mvp.ms_to_samples(self.cfg.min_separation_ms, self.sr))
            else:
                candidates = np.asarray([], dtype=np.int64)
            done += 1
            if self.is_cancelled():
                self.cancelled.emit(); return
            self.progress.emit(done, total_steps, self._status(timer, done, total_steps, f"{self.tr_texts['progress_candidates']}: {len(candidates)}"))

            events = mvp.evaluate_candidates(mono, self.sr, candidates, self.cfg)
            done += 1
            if self.is_cancelled():
                self.cancelled.emit(); return
            self.progress.emit(done, total_steps, self._status(timer, done, total_steps, f"{self.tr_texts['progress_events']}: {len(events)}"))
            self.finished_ok.emit(events, f"{self.tr_texts['detected_events_msg']}: {len(events)}")
        except Exception as e:
            self.failed.emit(f"{e}\n\n{traceback.format_exc()}")


class RepairWorker(CancelableWorker):
    progress = pyqtSignal(int, int, str)
    finished_ok = pyqtSignal(object, str)
    failed = pyqtSignal(str)

    def __init__(self, backend: LazyBackend, audio: np.ndarray, sr: int, events: Sequence[Any], cfg: Any, output_path: str, tr_texts: Dict[str, str]):
        super().__init__()
        self.backend = backend
        self.audio = audio
        self.sr = sr
        self.events = list(events)
        self.cfg = cfg
        self.output_path = output_path
        self.tr_texts = tr_texts

    def _status(self, timer: ProgressTimer, done: int, total: int) -> str:
        return f"{self.tr_texts['elapsed']}: {format_seconds(timer.elapsed())} / {self.tr_texts['remaining']}: {format_seconds(timer.eta(done, total))}"

    def run(self) -> None:
        try:
            ok, message = self.backend.load()
            if not ok:
                raise RuntimeError(message)
            mvp = self.backend.mvp
            repair_events = [ev for ev in self.events if getattr(ev, 'decision', '') == 'repair']
            total = max(2, len(repair_events) + 1)
            timer = ProgressTimer()
            self.progress.emit(0, total, self.tr_texts["status_repairing"])

            out = self.audio.copy().astype(np.float64)
            for i, ev in enumerate(repair_events, start=1):
                if self.is_cancelled():
                    self.cancelled.emit(); return
                out = mvp.apply_repairs(out, self.sr, [ev], self.cfg)
                self.progress.emit(i, total, self._status(timer, i, total))

            if self.is_cancelled():
                self.cancelled.emit(); return
            self.backend.sf.write(self.output_path, out, self.sr)
            self.progress.emit(total, total, self._status(timer, total, total))
            self.finished_ok.emit(out, self.output_path)
        except Exception as e:
            self.failed.emit(f"{e}\n\n{traceback.format_exc()}")


class WaveformWidget(pg.PlotWidget):
    def __init__(self):
        super().__init__()
        self.setBackground("#0b1220")
        self.showGrid(x=True, y=True, alpha=0.15)
        self.setMenuEnabled(False)
        self.setMouseEnabled(x=True, y=False)
        self.hideButtons()
        self.plotItem.setLabel("left", "Amplitude")
        self.plotItem.setLabel("bottom", "Time", units="s")
        self.curve = self.plot(pen=pg.mkPen(width=1))
        self.event_scatter = pg.ScatterPlotItem(size=8)
        self.addItem(self.event_scatter)
        self.current_line = pg.InfiniteLine(angle=90, movable=False)
        self.addItem(self.current_line)
        self.current_line.hide()
        self._times = np.array([], dtype=np.float64)
        self._audio = np.array([], dtype=np.float64)

    def set_audio(self, audio: np.ndarray, sr: int) -> None:
        times, preview = decimate_waveform(audio, sr)
        self._times = times
        self._audio = preview
        self.curve.setData(times, preview)
        self.event_scatter.setData([], [])
        if preview.size:
            self.autoRange()

    def set_events(self, events: Sequence[Any]) -> None:
        if not self._times.size:
            self.event_scatter.setData([], [])
            return
        xs = [float(getattr(ev, 'time_sec', 0.0)) for ev in events]
        ys = []
        for x in xs:
            idx = int(np.searchsorted(self._times, x))
            idx = max(0, min(self._audio.size - 1, idx))
            ys.append(float(self._audio[idx]))
        brushes = [pg.mkBrush("#22c55e") if getattr(ev, 'decision', '') == 'repair' else pg.mkBrush("#f59e0b") for ev in events]
        self.event_scatter.setData(xs, ys, brush=brushes, pen=None)

    def focus_time(self, time_sec: float, width_sec: float = 0.08) -> None:
        self.current_line.setValue(time_sec)
        self.current_line.show()
        self.setXRange(max(0.0, time_sec - width_sec), time_sec + width_sec, padding=0.02)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.language = "ko"
        self.backend = LazyBackend()
        self.audio: Optional[np.ndarray] = None
        self.repaired_audio: Optional[np.ndarray] = None
        self.sr: Optional[int] = None
        self.input_path: str = ""
        self.markers_path: str = ""
        self.events: List[Any] = []
        self.cfg: Any = None
        self.analyze_worker: Optional[AnalyzeWorker] = None
        self.repair_worker: Optional[RepairWorker] = None
        self.preview_process: Optional[subprocess.Popen] = None
        self.preview_temp_path: Optional[str] = None

        self.setWindowTitle(APP_TITLE)
        self.resize(1560, 980)
        self.setAcceptDrops(True)
        if ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(ICON_PATH)))

        self._build_ui()
        self._build_menu()
        self.setStyleSheet(DARK_QSS)
        self.apply_language()
        self._announce_backend_status()

    def tr_text(self, key: str) -> str:
        return LANG_TEXTS[self.language].get(key, key)

    def _build_ui(self) -> None:
        root = QWidget(); self.setCentralWidget(root)
        main_layout = QVBoxLayout(root); main_layout.setContentsMargins(16, 16, 16, 12); main_layout.setSpacing(12)
        self.title_label = QLabel(APP_TITLE); self.title_label.setObjectName("titleLabel")
        self.sub_label = QLabel(); self.sub_label.setObjectName("subLabel")
        self.drop_hint_label = QLabel(); self.drop_hint_label.setObjectName("dropHintLabel")
        main_layout.addWidget(self.title_label); main_layout.addWidget(self.sub_label); main_layout.addWidget(self.drop_hint_label)

        splitter = QSplitter(Qt.Orientation.Horizontal); main_layout.addWidget(splitter, 1)

        left = QWidget(); left_layout = QVBoxLayout(left); left_layout.setContentsMargins(0, 0, 0, 0); left_layout.setSpacing(12)
        self.file_group = QGroupBox(); file_form = QFormLayout(self.file_group)
        self.input_edit = DroppableLineEdit(); self.markers_edit = DroppableLineEdit(); self.output_edit = QLineEdit()
        self.input_edit.files_dropped.connect(self.handle_dropped_files); self.markers_edit.files_dropped.connect(self.handle_dropped_files)
        self.btn_open_audio = QPushButton(); self.btn_open_audio.clicked.connect(self.open_audio)
        self.btn_open_markers = QPushButton(); self.btn_open_markers.clicked.connect(self.open_markers)
        self.btn_browse_output = QPushButton(); self.btn_browse_output.clicked.connect(self.choose_output)
        row1 = QWidget(); l1 = QHBoxLayout(row1); l1.setContentsMargins(0,0,0,0); l1.addWidget(self.input_edit); l1.addWidget(self.btn_open_audio)
        row2 = QWidget(); l2 = QHBoxLayout(row2); l2.setContentsMargins(0,0,0,0); l2.addWidget(self.markers_edit); l2.addWidget(self.btn_open_markers)
        row3 = QWidget(); l3 = QHBoxLayout(row3); l3.setContentsMargins(0,0,0,0); l3.addWidget(self.output_edit); l3.addWidget(self.btn_browse_output)
        self.file_input_label = QLabel(); self.file_markers_label = QLabel(); self.file_output_label = QLabel()
        file_form.addRow(self.file_input_label, row1); file_form.addRow(self.file_markers_label, row2); file_form.addRow(self.file_output_label, row3)
        left_layout.addWidget(self.file_group)

        self.options_group = QGroupBox(); options_form = QFormLayout(self.options_group)
        self.easy_dial = QDial(); self.easy_dial.setRange(0, 100); self.easy_dial.setValue(55); self.easy_dial.setNotchesVisible(True)
        self.easy_dial.valueChanged.connect(self.update_easy_controls_from_dial)
        self.easy_value_label = QLabel(); self.easy_hint_label = QLabel()
        self.spin_crossfade = QDoubleSpinBox(); self.spin_crossfade.setRange(1.0, 20.0); self.spin_crossfade.setValue(4.0)
        self.spin_micro_fade = QDoubleSpinBox(); self.spin_micro_fade.setRange(0.2, 5.0); self.spin_micro_fade.setValue(1.0)
        self.spin_threshold = QDoubleSpinBox(); self.spin_threshold.setRange(0.1, 1.2); self.spin_threshold.setValue(0.55)
        self.spin_preview_ms = QDoubleSpinBox(); self.spin_preview_ms.setRange(100.0, 4000.0); self.spin_preview_ms.setValue(800.0)
        self.chk_auto = QCheckBox(); self.chk_auto.setChecked(True)
        self.chk_transient = QCheckBox(); self.chk_transient.setChecked(True)
        self.lang_combo = QComboBox(); self.lang_combo.addItem("한국어", "ko"); self.lang_combo.addItem("English", "en"); self.lang_combo.currentIndexChanged.connect(self.on_language_changed)
        self.options_easy_label = QLabel(); self.options_cf_label = QLabel(); self.options_mf_label = QLabel(); self.options_th_label = QLabel(); self.options_preview_label = QLabel(); self.options_lang_label = QLabel()
        easy_row = QWidget(); easy_layout = QHBoxLayout(easy_row); easy_layout.setContentsMargins(0, 0, 0, 0); easy_layout.addWidget(self.easy_dial); easy_layout.addWidget(self.easy_value_label)
        options_form.addRow(self.options_easy_label, easy_row)
        options_form.addRow(QLabel(), self.easy_hint_label)
        options_form.addRow(self.options_cf_label, self.spin_crossfade)
        options_form.addRow(self.options_mf_label, self.spin_micro_fade)
        options_form.addRow(self.options_th_label, self.spin_threshold)
        options_form.addRow(self.options_preview_label, self.spin_preview_ms)
        options_form.addRow(self.chk_auto)
        options_form.addRow(self.chk_transient)
        options_form.addRow(self.options_lang_label, self.lang_combo)
        left_layout.addWidget(self.options_group)

        self.run_group = QGroupBox(); run_layout = QVBoxLayout(self.run_group)
        row_run1 = QHBoxLayout(); row_run2 = QHBoxLayout(); row_run3 = QHBoxLayout()
        self.btn_analyze = QPushButton(); self.btn_analyze.clicked.connect(self.analyze)
        self.btn_cancel = QPushButton(); self.btn_cancel.clicked.connect(self.cancel_current_task)
        self.btn_export_report = QPushButton(); self.btn_export_report.clicked.connect(self.export_report)
        self.btn_repair_all = QPushButton(); self.btn_repair_all.clicked.connect(lambda: self.repair_and_save(False))
        self.btn_repair_selected = QPushButton(); self.btn_repair_selected.clicked.connect(lambda: self.repair_and_save(True))
        self.btn_preview_original = QPushButton(); self.btn_preview_original.clicked.connect(lambda: self.preview_selected(False))
        self.btn_preview_smoothed = QPushButton(); self.btn_preview_smoothed.clicked.connect(lambda: self.preview_selected(True))
        self.btn_stop_preview = QPushButton(); self.btn_stop_preview.clicked.connect(self.stop_preview)
        for b in (self.btn_analyze, self.btn_cancel, self.btn_export_report): row_run1.addWidget(b)
        for b in (self.btn_repair_all, self.btn_repair_selected): row_run2.addWidget(b)
        for b in (self.btn_preview_original, self.btn_preview_smoothed, self.btn_stop_preview): row_run3.addWidget(b)
        run_layout.addLayout(row_run1); run_layout.addLayout(row_run2); run_layout.addLayout(row_run3)
        left_layout.addWidget(self.run_group)

        self.status_group = QGroupBox(); status_layout = QVBoxLayout(self.status_group)
        self.status_label = QLabel(); self.progress_bar = QProgressBar(); self.progress_bar.setRange(0, 100); self.progress_detail_label = QLabel()
        status_layout.addWidget(self.status_label); status_layout.addWidget(self.progress_bar); status_layout.addWidget(self.progress_detail_label)
        left_layout.addWidget(self.status_group)

        self.log_group = QGroupBox(); log_layout = QVBoxLayout(self.log_group); self.log_box = QTextEdit(); self.log_box.setReadOnly(True); log_layout.addWidget(self.log_box)
        left_layout.addWidget(self.log_group, 1)
        splitter.addWidget(left)

        right = QWidget(); right_layout = QVBoxLayout(right); right_layout.setContentsMargins(0, 0, 0, 0); right_layout.setSpacing(12)
        self.wave_group = QGroupBox(); wave_layout = QVBoxLayout(self.wave_group); self.wave = WaveformWidget(); wave_layout.addWidget(self.wave); right_layout.addWidget(self.wave_group, 2)
        self.table_group = QGroupBox(); table_layout = QVBoxLayout(self.table_group); self.selection_info_label = QLabel(); self.table = QTableWidget(0, 6)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.itemSelectionChanged.connect(self.on_table_selection)
        table_layout.addWidget(self.selection_info_label); table_layout.addWidget(self.table); right_layout.addWidget(self.table_group, 2)
        splitter.addWidget(right); splitter.setSizes([560, 1000])

        self.footer = QLabel(DEV_FOOTER); self.footer.setObjectName("footerLabel"); self.footer.setAlignment(Qt.AlignmentFlag.AlignRight); main_layout.addWidget(self.footer)

    def _build_menu(self) -> None:
        self.action_quit = QAction(self); self.action_quit.triggered.connect(self.close)
        self.action_about = QAction(self); self.action_about.triggered.connect(self.show_about)
        self.action_check_backend = QAction(self); self.action_check_backend.triggered.connect(self.show_backend_status)
        self.menu_file = self.menuBar().addMenu(""); self.menu_file.addAction(self.action_quit)
        self.menu_tools = self.menuBar().addMenu(""); self.menu_tools.addAction(self.action_check_backend)
        self.menu_help = self.menuBar().addMenu(""); self.menu_help.addAction(self.action_about)

    def update_easy_controls_from_dial(self) -> None:
        v = self.easy_dial.value() / 100.0
        crossfade = 2.0 + (v * 8.0)
        micro_fade = 0.5 + (v * 1.8)
        threshold = 0.78 - (v * 0.35)
        self.spin_crossfade.setValue(round(crossfade, 2))
        self.spin_micro_fade.setValue(round(micro_fade, 2))
        self.spin_threshold.setValue(round(threshold, 2))
        self.easy_value_label.setText(str(self.easy_dial.value()))

    def apply_language(self) -> None:
        self.sub_label.setText(self.tr_text("subtitle")); self.drop_hint_label.setText(self.tr_text("drag_hint"))
        self.file_group.setTitle(self.tr_text("files")); self.file_input_label.setText(self.tr_text("input")); self.file_markers_label.setText(self.tr_text("markers")); self.file_output_label.setText(self.tr_text("output"))
        self.btn_open_audio.setText(self.tr_text("open_wav")); self.btn_open_markers.setText(self.tr_text("open_markers")); self.btn_browse_output.setText(self.tr_text("set_output")); self.output_edit.setPlaceholderText(self.tr_text("auto_output_ph"))
        self.options_group.setTitle(self.tr_text("options")); self.options_easy_label.setText(self.tr_text("easy_mode")); self.easy_hint_label.setText(self.tr_text("easy_hint")); self.options_cf_label.setText(self.tr_text("crossfade_ms")); self.options_mf_label.setText(self.tr_text("micro_fade_ms")); self.options_th_label.setText(self.tr_text("threshold")); self.options_preview_label.setText(self.tr_text("preview_ms")); self.chk_auto.setText(self.tr_text("auto_detect")); self.chk_transient.setText(self.tr_text("transient_protect")); self.options_lang_label.setText(self.tr_text("language"))
        self.run_group.setTitle(self.tr_text("run")); self.btn_analyze.setText(self.tr_text("analyze")); self.btn_cancel.setText(self.tr_text("cancel")); self.btn_export_report.setText(self.tr_text("save_report")); self.btn_repair_all.setText(self.tr_text("repair_save")); self.btn_repair_selected.setText(self.tr_text("repair_selected")); self.btn_preview_original.setText(self.tr_text("preview_original")); self.btn_preview_smoothed.setText(self.tr_text("preview_smoothed")); self.btn_stop_preview.setText(self.tr_text("stop_preview"))
        self.status_group.setTitle(self.tr_text("status")); self.log_group.setTitle(self.tr_text("log")); self.wave_group.setTitle(self.tr_text("waveform")); self.table_group.setTitle(self.tr_text("detected_events")); self.selection_info_label.setText(f"{self.tr_text('selection_count')}: 0")
        self.table.setHorizontalHeaderLabels([self.tr_text("time"), self.tr_text("score"), self.tr_text("rms_jump"), self.tr_text("corr_loss"), self.tr_text("spec"), self.tr_text("decision")])
        self.menu_file.setTitle(self.tr_text("file_menu")); self.menu_tools.setTitle(self.tr_text("tools_menu")); self.menu_help.setTitle(self.tr_text("help_menu")); self.action_quit.setText(self.tr_text("quit")); self.action_about.setText(self.tr_text("about")); self.action_check_backend.setText(self.tr_text("check_backend"))
        if self.progress_bar.value() == 0:
            self.status_label.setText(self.tr_text("idle")); self.progress_detail_label.setText("")
        self.update_easy_controls_from_dial()

    def on_language_changed(self) -> None:
        self.language = self.lang_combo.currentData(); self.apply_language()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls(): event.acceptProposedAction()
        else: event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if paths:
            self.handle_dropped_files(paths); event.acceptProposedAction()
        else:
            event.ignore()

    def handle_dropped_files(self, paths: List[str]) -> None:
        audio_exts = {".wav", ".aif", ".aiff"}; marker_exts = {".txt", ".csv"}; handled = False
        for path in paths:
            ext = Path(path).suffix.lower()
            if ext in audio_exts:
                self.load_audio_path(path); handled = True
            elif ext in marker_exts:
                self.markers_path = path; self.markers_edit.setText(path); self.log(f"{self.tr_text('loaded_markers')}: {path}"); handled = True
        if not handled:
            self.show_error(self.tr_text("status_error"), self.tr_text("drop_rejected"))

    def _announce_backend_status(self) -> None:
        ok, message = self.backend.load()
        if ok: self.log(self.tr_text("ready_backend"))
        else: self.log(self.tr_text("warn_backend")); self.log(message)

    def show_backend_status(self) -> None:
        ok, message = self.backend.load()
        if ok: self.show_info(self.tr_text("audio_backend"), self.tr_text("audio_backend_ok"))
        else: self.show_error(self.tr_text("audio_backend_unavailable"), message)

    def log(self, text: str) -> None:
        self.log_box.append(text)

    def show_error(self, title: str, message: str) -> None:
        QMessageBox.critical(self, title, message); self.log(f"[ERROR] {title}: {message}")

    def show_info(self, title: str, message: str) -> None:
        QMessageBox.information(self, title, message); self.log(f"[INFO] {title}: {message}")

    def require_backend(self) -> bool:
        ok, message = self.backend.load()
        if ok: return True
        self.show_error(self.tr_text("audio_backend_unavailable"), message); return False

    def set_busy(self, busy: bool) -> None:
        for w in (self.btn_analyze, self.btn_repair_all, self.btn_repair_selected, self.btn_export_report, self.btn_open_audio, self.btn_open_markers, self.btn_browse_output):
            w.setEnabled(not busy)
        self.btn_cancel.setEnabled(busy)

    def set_progress(self, done: int, total: int, detail: str, status_text: Optional[str] = None) -> None:
        pct = int(round((done / total) * 100)) if total > 0 else 0
        self.progress_bar.setValue(max(0, min(100, pct)))
        if status_text is not None: self.status_label.setText(status_text)
        self.progress_detail_label.setText(detail)

    def reset_progress(self) -> None:
        self.progress_bar.setValue(0); self.status_label.setText(self.tr_text("idle")); self.progress_detail_label.setText("")

    def current_config(self) -> Any:
        if not self.require_backend(): return None
        self.update_easy_controls_from_dial()
        return self.backend.mvp.RepairConfig(
            auto_detect=self.chk_auto.isChecked(),
            crossfade_ms=float(self.spin_crossfade.value()),
            micro_fade_ms=float(self.spin_micro_fade.value()),
            seam_threshold=float(self.spin_threshold.value()),
            sensitivity=0.7 + (self.easy_dial.value() / 100.0) * 1.6,
            protect_transients=self.chk_transient.isChecked(),
        )

    def ensure_output_path(self, selected_only: bool = False) -> str:
        output = self.output_edit.text().strip()
        if output:
            if selected_only:
                p = Path(output); return str(p.with_name(f"{p.stem}_selected{p.suffix or '.wav'}"))
            return output
        if not self.input_path: return ""
        p = Path(self.input_path)
        suffix = "_selected_smoothed.wav" if selected_only else "_smoothed.wav"
        out = p.with_name(f"{p.stem}{suffix}")
        self.output_edit.setText(str(p.with_name(f"{p.stem}_smoothed.wav")))
        return str(out)

    def open_audio(self) -> None:
        if not self.require_backend(): return
        path, _ = QFileDialog.getOpenFileName(self, self.tr_text("open_wav"), "", "Audio Files (*.wav *.aif *.aiff)")
        if path: self.load_audio_path(path)

    def load_audio_path(self, path: str) -> None:
        if not self.require_backend(): return
        try:
            audio, sr = self.backend.sf.read(path, always_2d=False)
            self.audio = audio; self.repaired_audio = None; self.sr = int(sr); self.input_path = path
            self.input_edit.setText(path); self.ensure_output_path(False)
            self.wave.set_audio(audio, self.sr); self.wave.set_events([]); self.events = []; self.table.setRowCount(0); self.update_selection_info(); self.reset_progress()
            self.log(f"{self.tr_text('loaded_audio')}: {path}"); self.log(f"{self.tr_text('sample_rate')}: {sr} Hz"); self.log(f"{self.tr_text('channels')}: {1 if audio.ndim == 1 else audio.shape[1]}")
        except Exception as e:
            self.show_error(self.tr_text("open_audio_failed"), f"{e}\n\n{traceback.format_exc()}")

    def open_markers(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, self.tr_text("open_markers"), "", "Text Files (*.txt);;CSV Files (*.csv);;All Files (*)")
        if path:
            self.markers_path = path; self.markers_edit.setText(path); self.log(f"{self.tr_text('loaded_markers')}: {path}")

    def choose_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, self.tr_text("set_output"), self.output_edit.text().strip() or "smoothed.wav", "WAV Files (*.wav)")
        if path: self.output_edit.setText(path)

    def analyze(self) -> None:
        if self.audio is None or self.sr is None:
            self.show_error(self.tr_text("analyze_failed"), self.tr_text("need_open_wav")); return
        cfg = self.current_config()
        if cfg is None: return
        self.cfg = cfg
        if self.markers_path:
            self.chk_auto.setChecked(False)
            self.cfg.auto_detect = False
        self.set_busy(True); self.set_progress(0, 100, "", self.tr_text("status_analyzing"))
        self.analyze_worker = AnalyzeWorker(self.backend, self.audio, self.sr, self.markers_path, self.cfg, LANG_TEXTS[self.language])
        self.analyze_worker.progress.connect(self.on_analyze_progress)
        self.analyze_worker.finished_ok.connect(self.on_analyze_finished)
        self.analyze_worker.failed.connect(self.on_analyze_failed)
        self.analyze_worker.cancelled.connect(self.on_task_cancelled)
        self.analyze_worker.start()

    def on_analyze_progress(self, done: int, total: int, detail: str) -> None:
        self.set_progress(done, total, detail, self.tr_text("status_analyzing"))

    def on_analyze_finished(self, events: List[Any], summary: str) -> None:
        self.events = events; self.populate_table(); self.wave.set_events(events)
        repair_count = sum(1 for e in events if getattr(e, 'decision', '') == 'repair'); skip_count = len(events) - repair_count
        self.log(f"Total seams: {len(events)} / Repair: {repair_count} / Skip: {skip_count}")
        self.set_progress(100, 100, summary, self.tr_text("status_done")); self.set_busy(False)
        self.show_info(self.tr_text("analyze_complete"), f"{self.tr_text('detected_events_msg')}: {len(events)}\nRepair: {repair_count}\nSkip: {skip_count}")

    def on_analyze_failed(self, message: str) -> None:
        self.set_progress(0, 100, message, self.tr_text("status_error")); self.set_busy(False); self.show_error(self.tr_text("analyze_failed"), message)

    def populate_table(self) -> None:
        self.table.setRowCount(len(self.events))
        repair_brush = QBrush(QColor("#22c55e")); skip_brush = QBrush(QColor("#f59e0b"))
        for row, ev in enumerate(self.events):
            values = [
                f"{float(getattr(ev, 'time_sec', 0.0)):.6f}",
                f"{float(getattr(ev, 'seam_score', 0.0)):.3f}",
                f"{float(getattr(ev, 'rms_jump', 0.0)):.3f}",
                f"{float(getattr(ev, 'corr_loss', 0.0)):.3f}",
                f"{float(getattr(ev, 'spectral_mismatch', 0.0)):.3f}",
                str(getattr(ev, 'decision', '')),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value); item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if col == 5: item.setForeground(repair_brush if getattr(ev, 'decision', '') == 'repair' else skip_brush)
                self.table.setItem(row, col, item)
        self.update_selection_info()

    def get_selected_rows(self) -> List[int]:
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        return sorted({r.row() for r in rows})

    def get_selected_events(self) -> List[Any]:
        return [self.events[r] for r in self.get_selected_rows() if 0 <= r < len(self.events)]

    def update_selection_info(self) -> None:
        self.selection_info_label.setText(f"{self.tr_text('selection_count')}: {len(self.get_selected_rows())}")

    def on_table_selection(self) -> None:
        rows = self.get_selected_rows()
        if rows:
            row = rows[0]
            if 0 <= row < len(self.events): self.wave.focus_time(float(getattr(self.events[row], 'time_sec', 0.0)))
        self.update_selection_info()

    def cancel_current_task(self) -> None:
        if self.analyze_worker and self.analyze_worker.isRunning(): self.analyze_worker.cancel(); return
        if self.repair_worker and self.repair_worker.isRunning(): self.repair_worker.cancel(); return
        self.stop_preview()

    def on_task_cancelled(self) -> None:
        self.set_busy(False); self.set_progress(0, 100, "", self.tr_text("status_cancelled")); self.log(f"[INFO] {self.tr_text('status_cancelled')}")

    def repair_and_save(self, selected_only: bool) -> None:
        if self.audio is None or self.sr is None:
            self.show_error(self.tr_text("repair_failed"), self.tr_text("need_open_wav")); return
        if not self.events:
            self.show_error(self.tr_text("repair_failed"), self.tr_text("need_analyze_first")); return
        if not self.require_backend(): return
        target_events = self.get_selected_events() if selected_only else self.events
        if selected_only and not target_events:
            self.show_error(self.tr_text("repair_failed"), self.tr_text("need_select_event")); return
        output_path = self.ensure_output_path(selected_only)
        if not output_path:
            self.show_error(self.tr_text("repair_failed"), self.tr_text("need_output_path")); return
        cfg = self.current_config()
        if cfg is None: return
        self.cfg = cfg
        self.set_busy(True); self.set_progress(0, 100, "", self.tr_text("status_repairing"))
        self.repair_worker = RepairWorker(self.backend, self.audio, self.sr, target_events, self.cfg, output_path, LANG_TEXTS[self.language])
        self.repair_worker.progress.connect(self.on_repair_progress)
        self.repair_worker.finished_ok.connect(self.on_repair_finished)
        self.repair_worker.failed.connect(self.on_repair_failed)
        self.repair_worker.cancelled.connect(self.on_task_cancelled)
        self.repair_worker.start()

    def on_repair_progress(self, done: int, total: int, detail: str) -> None:
        self.set_progress(done, total, detail, self.tr_text("status_repairing"))

    def on_repair_finished(self, repaired: Any, output_path: str) -> None:
        self.repaired_audio = repaired; repair_count = sum(1 for e in self.events if getattr(e, 'decision', '') == 'repair')
        self.log(f"{self.tr_text('saved')}: {output_path}")
        self.set_progress(100, 100, output_path, self.tr_text("status_done")); self.set_busy(False)
        self.show_info(self.tr_text("repair_complete"), f"{self.tr_text('saved')}: {output_path}\n{self.tr_text('applied_repairs')}: {repair_count}")

    def on_repair_failed(self, message: str) -> None:
        self.set_progress(0, 100, message, self.tr_text("status_error")); self.set_busy(False); self.show_error(self.tr_text("repair_failed"), message)

    def export_report(self) -> None:
        if not self.events:
            self.show_error(self.tr_text("export_failed"), self.tr_text("need_analyze_first")); return
        try:
            path, _ = QFileDialog.getSaveFileName(self, self.tr_text("save_report"), "seam_report.csv", "CSV Files (*.csv)")
            if not path: return
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(["time_sec", "seam_score", "rms_jump", "corr_loss", "spectral_mismatch", "decision"])
                for ev in self.events:
                    writer.writerow([getattr(ev, 'time_sec', 0.0), getattr(ev, 'seam_score', 0.0), getattr(ev, 'rms_jump', 0.0), getattr(ev, 'corr_loss', 0.0), getattr(ev, 'spectral_mismatch', 0.0), getattr(ev, 'decision', '')])
            self.log(f"{self.tr_text('saved_report')}: {path}"); self.show_info(self.tr_text("export_complete"), f"{self.tr_text('saved_report')}: {path}")
        except Exception as e:
            self.show_error(self.tr_text("export_failed"), f"{e}\n\n{traceback.format_exc()}")

    def _preview_command(self) -> Optional[str]:
        if sys.platform == "darwin" and shutil.which("afplay"): return "afplay"
        return None

    def stop_preview(self) -> None:
        if self.preview_process is not None:
            try: self.preview_process.terminate()
            except Exception: pass
            self.preview_process = None
        if self.preview_temp_path and os.path.exists(self.preview_temp_path):
            try: os.remove(self.preview_temp_path)
            except Exception: pass
            self.preview_temp_path = None
        self.log(self.tr_text("preview_stopped"))

    def _make_preview_segment(self, smoothed: bool) -> Tuple[np.ndarray, int]:
        if self.audio is None or self.sr is None: raise RuntimeError(self.tr_text("need_open_wav"))
        selected = self.get_selected_events()
        if not selected: raise RuntimeError(self.tr_text("need_select_event"))
        ev = selected[0]
        center = int(getattr(ev, 'sample_index', 0))
        half = int(round((self.spin_preview_ms.value() / 1000.0) * self.sr * 0.5))
        a = max(0, center - half); b = min(len(self.audio), center + half)
        if smoothed:
            cfg = self.current_config()
            if cfg is None: raise RuntimeError(self.tr_text("audio_backend_unavailable"))
            seg_audio = self.backend.mvp.apply_repairs(self.audio, self.sr, [ev], cfg)
            seg = seg_audio[a:b]
        else:
            seg = self.audio[a:b]
        return seg, self.sr

    def preview_selected(self, smoothed: bool) -> None:
        if not self.require_backend(): return
        cmd = self._preview_command()
        if not cmd:
            self.show_error(self.tr_text("status_error"), self.tr_text("preview_not_available")); return
        try:
            seg, sr = self._make_preview_segment(smoothed)
            self.stop_preview()
            fd, path = tempfile.mkstemp(suffix=".wav", prefix="seam_preview_"); os.close(fd)
            self.backend.sf.write(path, seg, sr)
            self.preview_temp_path = path
            self.preview_process = subprocess.Popen([cmd, path])
            self.status_label.setText(self.tr_text("status_previewing")); self.progress_detail_label.setText(path); self.log(f"{self.tr_text('preview_started')}: {path}")
        except Exception as e:
            self.show_error(self.tr_text("status_error"), f"{e}\n\n{traceback.format_exc()}")

    def show_about(self) -> None:
        QMessageBox.information(self, self.tr_text("about"), self.tr_text("about_body"))

    def closeEvent(self, event) -> None:
        self.stop_preview(); super().closeEvent(event)


class HelperTests(unittest.TestCase):
    def test_format_seconds(self) -> None:
        self.assertEqual(format_seconds(0), "00:00")
        self.assertEqual(format_seconds(65), "01:05")
        self.assertEqual(format_seconds(3661), "1:01:01")

    def test_decimate_waveform_limits_points(self) -> None:
        x = np.linspace(-1.0, 1.0, 500_000, dtype=np.float32)
        times, preview = decimate_waveform(x, sr=48000, max_points=1000)
        self.assertLessEqual(preview.size, 1000)
        self.assertEqual(times.size, preview.size)

    def test_easy_dial_mapping(self) -> None:
        class Dummy:
            pass
        d = Dummy()
        d.easy_dial = Dummy(); d.easy_dial.value = lambda: 50
        d.spin_crossfade = Dummy(); d.spin_crossfade.setValue = lambda v: setattr(d, 'cf', v)
        d.spin_micro_fade = Dummy(); d.spin_micro_fade.setValue = lambda v: setattr(d, 'mf', v)
        d.spin_threshold = Dummy(); d.spin_threshold.setValue = lambda v: setattr(d, 'th', v)
        d.easy_value_label = Dummy(); d.easy_value_label.setText = lambda v: setattr(d, 'label', v)
        MainWindow.update_easy_controls_from_dial(d)
        self.assertGreater(d.cf, 2.0)
        self.assertGreater(d.mf, 0.5)
        self.assertLess(d.th, 0.78)


def run_self_tests() -> int:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(HelperTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=APP_TITLE)
    parser.add_argument("--self-test", action="store_true", help="run lightweight self tests and exit")
    args = parser.parse_args(argv)
    if args.self_test:
        return run_self_tests()
    pg.setConfigOptions(antialias=False)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    if ICON_PATH.exists(): app.setWindowIcon(QIcon(str(ICON_PATH)))
    win = MainWindow(); win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
