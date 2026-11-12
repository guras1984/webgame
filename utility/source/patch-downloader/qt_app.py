"""Native Windows desktop UI for KJ Patch Downloader."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import threading
import certifi

os.environ.setdefault("SSL_CERT_FILE", certifi.where())

from PySide6.QtCore import Qt, QDate, QThread, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDateEdit, QFileDialog, QFrame,
    QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMessageBox, QProgressBar, QPushButton,
    QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
    QHeaderView, QAbstractItemView, QPlainTextEdit
)

from catalog import Catalog, Cancelled
from downloads import download_all

STYLE = """
QWidget { font-family: "Segoe UI"; font-size: 10pt; color: #243348; }
QMainWindow, QDialog { background: #f4f6f9; }
QGroupBox { background: white; border: 1px solid #dce2ea; border-radius: 10px;
  margin-top: 12px; padding: 12px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; color: #38516f; }
QPushButton { background: white; border: 1px solid #d3dbe5; border-radius: 7px; padding: 8px 13px; }
QPushButton:hover { background: #e8eef6; }
QPushButton:disabled { color: #8c97a6; background: #e9edf2; }
QPushButton#primary { background: #17334f; color: white; border: 0; font-weight: 600; }
QLineEdit, QPlainTextEdit, QListWidget, QComboBox, QDateEdit, QTableWidget {
  background: white; border: 1px solid #d4dce7; border-radius: 6px; padding: 5px;
  selection-background-color: #dce8f5; selection-color: #152a45; }
QHeaderView::section { background: #eef2f7; border: 0; padding: 8px; color: #51647c; font-weight: 600; }
QLabel#title { font-size: 23pt; font-weight: 700; color: #172d48; }
QLabel#muted { color: #63748b; }
QLabel#status { color: #41566f; padding: 4px; }
QProgressBar { height: 12px; border: 0; border-radius: 6px; background: #e3e9f0; text-align: center; }
QProgressBar::chunk { background: #bd7a45; border-radius: 6px; }
"""


class Task(QThread):
    completed = Signal(str, object)
    failed = Signal(str, str)
    status = Signal(str)
    progress = Signal(str, int, int, int, int)
    results_changed = Signal(object)

    def __init__(self, operation, work):
        super().__init__()
        self.operation = operation
        self.work = work
        self.cancel = threading.Event()

    def run(self):
        try:
            result = self.work(self)
            self.completed.emit(self.operation, result)
        except Cancelled as exc:
            self.failed.emit(self.operation, str(exc) or "작업을 중단했습니다.")
        except Exception as exc:
            self.failed.emit(self.operation, str(exc))


def make_button(text, primary=False):
    button = QPushButton(text)
    if primary:
        button.setObjectName("primary")
    return button


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("KJ Patch Downloader")
        self.setMinimumSize(920, 680)
        self.resize(1160, 820)
        icon = Path(__file__).resolve().parent / "assets" / "KJ-TOOL.ico"
        if icon.exists():
            self.setWindowIcon(QIcon(str(icon)))
        self.task = None
        self.updates = []
        self.plan = None
        self.results = []
        self._build_ui()
        self._set_dates()

    def _build_ui(self):
        outer = QWidget()
        layout = QVBoxLayout(outer)
        layout.setContentsMargins(24, 20, 24, 18)
        layout.setSpacing(14)

        header = QHBoxLayout()
        brand = QLabel("KJ TOOL")
        brand.setStyleSheet("font-size: 9pt; letter-spacing: 2px; color: #bd7a45; font-weight: 700;")
        header.addWidget(brand)
        header.addStretch(1)
        header.addWidget(QLabel("Windows Server 업데이트 다운로드"))
        layout.addLayout(header)

        title = QLabel("서버 패치를 한곳에.")
        title.setObjectName("title")
        layout.addWidget(title)
        subtitle = QLabel("서버 버전과 날짜를 고르고, 필요한 파일을 모아 받으세요.")
        subtitle.setObjectName("muted")
        layout.addWidget(subtitle)

        criteria = QGroupBox("조회 조건")
        grid = QGridLayout(criteria)
        self.version = QComboBox()
        self.version.addItems(["2016", "2019", "2022", "2025"])
        self.version.setCurrentText("2022")
        self.since = QDateEdit()
        self.since.setCalendarPopup(True)
        self.since.setDisplayFormat("yyyy-MM-dd")
        self.until = QDateEdit()
        self.until.setCalendarPopup(True)
        self.until.setDisplayFormat("yyyy-MM-dd")
        self.inclusive = QCheckBox("기준일 당일 포함")
        self.dotnet = QCheckBox(".NET 업데이트 포함")
        self.dotnet.setChecked(True)
        self.preview = QCheckBox("미리보기 포함")
        self.search_button = make_button("업데이트 조회", True)
        self.search_button.clicked.connect(self.search)
        grid.addWidget(QLabel("대상 서버"), 0, 0)
        grid.addWidget(self.version, 0, 1)
        grid.addWidget(QLabel("기준일"), 0, 2)
        grid.addWidget(self.since, 0, 3)
        grid.addWidget(QLabel("종료일"), 0, 4)
        grid.addWidget(self.until, 0, 5)
        grid.addWidget(self.search_button, 0, 6)
        options = QHBoxLayout()
        options.addWidget(self.inclusive)
        options.addWidget(self.dotnet)
        options.addWidget(self.preview)
        options.addStretch(1)
        options.addWidget(QLabel("x64 · 일반 LTSC"))
        grid.addLayout(options, 1, 0, 1, 7)
        note = QLabel("날짜 기준은 Microsoft 카탈로그의 게시·갱신일(Last Updated)입니다. 최초 출시일과 다를 수 있습니다.")
        note.setObjectName("muted")
        note.setWordWrap(True)
        grid.addWidget(note, 2, 0, 1, 7)
        layout.addWidget(criteria)

        status_row = QHBoxLayout()
        self.status_label = QLabel("서버와 기준일을 선택해 주세요.")
        self.status_label.setObjectName("status")
        self.cancel_button = make_button("작업 중단")
        self.cancel_button.clicked.connect(self.cancel)
        self.cancel_button.setEnabled(False)
        status_row.addWidget(self.status_label, 1)
        status_row.addWidget(self.cancel_button)
        layout.addLayout(status_row)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.hide()
        layout.addWidget(self.progress)

        split = QSplitter(Qt.Orientation.Vertical)
        updates_box = QGroupBox("업데이트")
        updates_layout = QVBoxLayout(updates_box)
        update_buttons = QHBoxLayout()
        self.select_all_button = make_button("전체 선택")
        self.select_none_button = make_button("선택 해제")
        self.prepare_button = make_button("선택 항목 파일 확인", True)
        self.select_all_button.clicked.connect(lambda: self._select_updates(True))
        self.select_none_button.clicked.connect(lambda: self._select_updates(False))
        self.prepare_button.clicked.connect(self.prepare)
        update_buttons.addWidget(self.select_all_button)
        update_buttons.addWidget(self.select_none_button)
        update_buttons.addStretch(1)
        update_buttons.addWidget(self.prepare_button)
        updates_layout.addLayout(update_buttons)

        self.update_table = QTableWidget(0, 5)
        self.update_table.setHorizontalHeaderLabels(["선택", "업데이트", "게시·갱신일", "크기", "공식 정보"])
        self.update_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.update_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.update_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.update_table.setColumnWidth(0, 52)
        self.update_table.setColumnWidth(2, 120)
        self.update_table.setColumnWidth(3, 100)
        self.update_table.setColumnWidth(4, 110)
        self.update_table.itemChanged.connect(lambda *_: self._refresh_buttons())
        updates_layout.addWidget(self.update_table)
        split.addWidget(updates_box)

        plan_box = QGroupBox("다운로드 파일")
        plan_layout = QVBoxLayout(plan_box)
        plan_header = QHBoxLayout()
        self.prerequisites = QCheckBox("선행·권장 패치도 함께 다운로드")
        self.prerequisites.setChecked(True)
        self.prerequisites.stateChanged.connect(self._toggle_prerequisites)
        plan_header.addWidget(self.prerequisites)
        plan_header.addStretch(1)
        plan_layout.addLayout(plan_header)

        self.plan_warnings = QLabel("")
        self.plan_warnings.setWordWrap(True)
        self.plan_warnings.setStyleSheet("color:#9a4c34; background:#fff5ee; padding:8px; border-radius:6px;")
        self.plan_warnings.hide()
        plan_layout.addWidget(self.plan_warnings)
        self.notes = QPlainTextEdit()
        self.notes.setReadOnly(True)
        self.notes.setMaximumHeight(74)
        self.notes.hide()
        plan_layout.addWidget(self.notes)
        self.file_list = QListWidget()
        plan_layout.addWidget(self.file_list)

        folder_row = QHBoxLayout()
        self.folder = QLineEdit()
        self.folder.setPlaceholderText("패치 저장 폴더")
        self.folder.setText(str(Path.home() / "Downloads" / "KJ-Patches"))
        self.browse_button = make_button("폴더 선택")
        self.open_folder_button = make_button("폴더 열기")
        self.download_button = make_button("선택 파일 다운로드", True)
        self.browse_button.clicked.connect(self.choose_folder)
        self.open_folder_button.clicked.connect(self.open_folder)
        self.download_button.clicked.connect(self.download)
        folder_row.addWidget(QLabel("저장 폴더"))
        folder_row.addWidget(self.folder, 1)
        folder_row.addWidget(self.browse_button)
        folder_row.addWidget(self.open_folder_button)
        folder_row.addWidget(self.download_button)
        plan_layout.addLayout(folder_row)
        split.addWidget(plan_box)

        results_box = QGroupBox("다운로드 결과")
        results_layout = QVBoxLayout(results_box)
        result_header = QHBoxLayout()
        result_header.addWidget(QLabel("파일별 검증 결과는 JSON·CSV로 저장됩니다."))
        result_header.addStretch(1)
        self.retry_button = make_button("실패 항목 다시 받기")
        self.retry_button.clicked.connect(self.retry)
        result_header.addWidget(self.retry_button)
        results_layout.addLayout(result_header)
        self.result_table = QTableWidget(0, 3)
        self.result_table.setHorizontalHeaderLabels(["결과", "파일명", "KB"])
        self.result_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        results_layout.addWidget(self.result_table)
        split.addWidget(results_box)
        split.setSizes([360, 310, 150])
        layout.addWidget(split, 1)

        footer = QLabel("Microsoft 공식 카탈로그에서 조회 · SHA 검증 후 저장 · KJ TOOL")
        footer.setAlignment(Qt.AlignmentFlag.AlignRight)
        footer.setObjectName("muted")
        layout.addWidget(footer)
        self.setCentralWidget(outer)
        self._refresh_buttons()

    def _set_dates(self):
        today = QDate.currentDate()
        self.until.setDate(today)
        self.since.setDate(today.addDays(-90))
        self.since.setMinimumDate(QDate(2016, 1, 1))
        self.until.setMinimumDate(QDate(2016, 1, 1))
        self.since.setMaximumDate(today)
        self.until.setMaximumDate(today)

    def _set_busy(self, busy):
        for widget in (self.version, self.since, self.until, self.inclusive, self.dotnet, self.preview,
                       self.select_all_button, self.select_none_button, self.prepare_button,
                       self.prerequisites, self.file_list, self.folder, self.browse_button,
                       self.open_folder_button, self.download_button, self.retry_button):
            widget.setEnabled(not busy)
        self.search_button.setEnabled(not busy)
        self.cancel_button.setEnabled(busy)
        if busy:
            self.progress.show()
            self.progress.setRange(0, 0)
        else:
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
        self._refresh_buttons()

    def _refresh_buttons(self):
        busy = self.task is not None
        if not busy:
            self.prepare_button.setEnabled(bool(self._selected_updates()))
            self.download_button.setEnabled(bool(self._selected_files()))
            self.retry_button.setEnabled(any(not item.get("success") for item in self.results))

    def _selected_updates(self):
        chosen = set()
        for row in range(self.update_table.rowCount()):
            checkbox = self.update_table.item(row, 0)
            if checkbox and checkbox.checkState() == Qt.CheckState.Checked:
                chosen.add(checkbox.data(Qt.ItemDataRole.UserRole))
        return [item for item in self.updates if item["id"] in chosen]

    def _selected_files(self):
        chosen = set()
        for row in range(self.file_list.count()):
            entry = self.file_list.item(row)
            if entry.checkState() == Qt.CheckState.Checked:
                chosen.add(entry.data(Qt.ItemDataRole.UserRole))
        return [f for f in (self.plan or {}).get("files", []) if f["key"] in chosen]

    def _select_updates(self, enabled):
        state = Qt.CheckState.Checked if enabled else Qt.CheckState.Unchecked
        for row in range(self.update_table.rowCount()):
            self.update_table.item(row, 0).setCheckState(state)

    def _worker(self, operation, work):
        self.status_label.setText("작업 중…")
        self.task = Task(operation, work)
        self._set_busy(True)
        self.task.status.connect(self.status_label.setText)
        self.task.progress.connect(self._progress_update)
        self.task.results_changed.connect(self._show_results)
        self.task.completed.connect(self._complete)
        self.task.failed.connect(self._failed)
        self.task.start()

    def search(self):
        version = self.version.currentText()
        since = self.since.date().toString(Qt.DateFormat.ISODate)
        until = self.until.date().toString(Qt.DateFormat.ISODate)
        if since > until:
            QMessageBox.warning(self, "날짜 확인", "기준일은 종료일보다 앞서야 합니다.")
            return
        inclusive, dotnet, preview = self.inclusive.isChecked(), self.dotnet.isChecked(), self.preview.isChecked()
        def work(task):
            catalog = Catalog(task.cancel, task.status.emit)
            return catalog.search(version, since, until, inclusive, dotnet, preview)
        self._worker("search", work)

    def prepare(self):
        updates = self._selected_updates()
        if not updates:
            return
        version = self.version.currentText()
        def work(task):
            catalog = Catalog(task.cancel, task.status.emit)
            return catalog.plan(updates, version)
        self._worker("plan", work)

    def _download(self, items):
        folder = self.folder.text().strip()
        if not folder:
            QMessageBox.warning(self, "저장 폴더", "저장 폴더를 선택해 주세요.")
            return
        def work(task):
            return download_all(
                items, folder, task.cancel,
                task.progress.emit,
                lambda results: task.results_changed.emit(list(results))
            )
        self._worker("download", work)

    def download(self):
        items = self._selected_files()
        if items:
            self._download(items)

    def retry(self):
        failed = [item for item in self.results if not item.get("success")]
        if failed:
            self._download(failed)

    def cancel(self):
        if self.task and self.task.isRunning():
            self.task.cancel.set()
            self.status_label.setText("작업을 중단하고 있습니다…")

    def choose_folder(self):
        current = self.folder.text().strip() or str(Path.home() / "Downloads")
        selected = QFileDialog.getExistingDirectory(self, "패치 저장 폴더 선택", current)
        if selected:
            self.folder.setText(selected)

    def open_folder(self):
        folder = Path(self.folder.text().strip()).expanduser()
        if not folder.is_dir():
            QMessageBox.information(self, "폴더 열기", "다운로드 후 저장 폴더를 열 수 있습니다.")
            return
        if os.name == "nt":
            os.startfile(str(folder))
        else:
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(folder)])

    def _complete(self, operation, result):
        if operation == "search":
            self.updates = result
            self.plan = None
            self.results = []
            self._render_updates()
            self._render_plan()
            self._show_results([])
            self.status_label.setText(f"{len(result)}건 조회 완료" if result else "선택한 기간에 해당하는 업데이트가 없습니다.")
        elif operation == "plan":
            self.plan = result
            self._render_plan()
            self.status_label.setText(f"다운로드 파일 {len(result.get('files', []))}개 확인 완료")
        elif operation == "download":
            self.results = result
            self._show_results(result)
            succeeded = sum(bool(item.get("success")) for item in result)
            self.status_label.setText(f"검증 완료 {succeeded}/{len(result)}개")
        self.task = None
        self._set_busy(False)

    def _failed(self, operation, message):
        self.task = None
        self._set_busy(False)
        self.status_label.setText("작업을 완료하지 못했습니다.")
        QMessageBox.warning(self, "KJ Patch Downloader", message)

    def _progress_update(self, message, received, total, index, count):
        self.status_label.setText(f"{index + 1}/{count} 파일 · {message}")
        if total:
            self.progress.setRange(0, 100)
            self.progress.setValue(min(100, int(received * 100 / total)))
        else:
            self.progress.setRange(0, 0)

    def _render_updates(self):
        self.update_table.blockSignals(True)
        self.update_table.setRowCount(len(self.updates))
        for row, update in enumerate(self.updates):
            check = QTableWidgetItem()
            check.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            check.setCheckState(Qt.CheckState.Unchecked)
            check.setData(Qt.ItemDataRole.UserRole, update["id"])
            self.update_table.setItem(row, 0, check)
            title = QTableWidgetItem(update["title"] + "\n" + update.get("classification", ""))
            title.setToolTip(update.get("products", ""))
            self.update_table.setItem(row, 1, title)
            self.update_table.setItem(row, 2, QTableWidgetItem(update["date"]))
            self.update_table.setItem(row, 3, QTableWidgetItem(self._size(update.get("size", 0))))
            link = QLabel(f'<a href="{update["url"]}">{update.get("kb") or "Catalog"}</a>')
            link.setOpenExternalLinks(True)
            self.update_table.setCellWidget(row, 4, link)
        self.update_table.blockSignals(False)
        self._refresh_buttons()

    def _render_plan(self):
        self.file_list.clear()
        if not self.plan:
            self.plan_warnings.hide()
            self.notes.hide()
            return
        for file in self.plan.get("files", []):
            tag = "선행·권장" if file.get("prerequisite") else "선택 업데이트"
            detail = f'{file.get("kb", "")} · {file.get("date") or "날짜 확인 필요"} · {file.get("algorithm", "").upper()} 검증'
            entry = QListWidgetItem(f'{tag}   {file["name"]}\n{detail}')
            entry.setFlags(entry.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            entry.setCheckState(Qt.CheckState.Checked)
            entry.setData(Qt.ItemDataRole.UserRole, file["key"])
            entry.setData(Qt.ItemDataRole.UserRole + 1, bool(file.get("prerequisite")))
            self.file_list.addItem(entry)
        warnings = self.plan.get("warnings", [])
        self.plan_warnings.setText("\n".join(warnings))
        self.plan_warnings.setVisible(bool(warnings))
        notes = self.plan.get("notes", [])
        if notes:
            self.notes.setPlainText("\n\n".join(f'{note["kb"]}: {note["text"]}\n{note["url"]}' for note in notes))
            self.notes.show()
        else:
            self.notes.hide()
        self._refresh_buttons()

    def _toggle_prerequisites(self, state):
        enabled = state == Qt.CheckState.Checked.value
        for row in range(self.file_list.count()):
            entry = self.file_list.item(row)
            if entry.data(Qt.ItemDataRole.UserRole + 1):
                entry.setCheckState(Qt.CheckState.Checked if enabled else Qt.CheckState.Unchecked)
        self._refresh_buttons()

    def _show_results(self, results):
        self.result_table.setRowCount(len(results))
        for row, item in enumerate(results):
            status = item.get("status", "검증 중")
            self.result_table.setItem(row, 0, QTableWidgetItem(status))
            self.result_table.setItem(row, 1, QTableWidgetItem(item.get("name", "")))
            self.result_table.setItem(row, 2, QTableWidgetItem(item.get("kb", "")))
        self.results = results
        self._refresh_buttons()

    @staticmethod
    def _size(value):
        if value >= 1024 ** 3:
            return f"{value / 1024 ** 3:.2f} GB"
        return f"{value / 1024 ** 2:.1f} MB"

    def closeEvent(self, event):
        if self.task and self.task.isRunning():
            answer = QMessageBox.question(self, "작업 중", "다운로드 작업을 중단하고 종료할까요?")
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.task.cancel.set()
            self.task.wait()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("KJ Patch Downloader")
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

