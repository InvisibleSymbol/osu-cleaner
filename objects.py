import datetime
import os
import shutil
import time
from itertools import chain
from pathlib import Path

from PyQt5.QtCore import pyqtSignal, QObject
from PyQt5.QtWidgets import QPushButton, QFileDialog, QFrame, QHBoxLayout, QLabel, QCheckBox, QSizePolicy, QGridLayout
from osu import CollectionDb, ScoresDb

from utils import SmallOsuDb


class FolderButton(QPushButton):
    path_chosen_signal = pyqtSignal(Path)  # emits the selected path

    def __init__(self, text):
        super().__init__()
        self.selection_made = False
        self.path = None
        self.setText(text)
        self.dialog = QFileDialog(self)
        self.dialog.setFileMode(QFileDialog.Directory)
        self.dialog.finished.connect(self.process_selection)
        self.clicked.connect(self.dialog.open)

    def process_selection(self):
        # do nothing if the user pressed cancel
        if not self.dialog.result():
            return
        files = self.dialog.selectedFiles()
        path = files[0]
        path = Path(path)
        self.path = path
        self.path_chosen_signal.emit(path)


class Filter(QFrame):
    path_chosen_signal = pyqtSignal(Path)  # emits the selected path

    def __init__(self, label, filter_name):
        super().__init__()
        self.label = label
        self.filter_name = filter_name
        self.toggle = QCheckBox(self)
        self.toggle.setCheckState(2)
        self.name = QLabel(f"{label} - ??? Hashes")
        self.name.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.layout = QHBoxLayout()
        self.layout.addWidget(self.toggle)
        self.layout.addWidget(self.name)
        self.layout.setContentsMargins(10, 10, 10, 0)
        self.setLayout(self.layout)

    def update_hash_count(self, value):
        self.name.setText(f"{self.label} - {value} Hashes")


class MultiWidget(QFrame):
    def __init__(self, *widgets):
        QFrame.__init__(self)
        self.layout = QHBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        for widget in widgets:
            self.layout.addWidget(widget)
        self.setLayout(self.layout)


class BottomWidget(QFrame):
    def __init__(self, w1, w2, w3):
        QFrame.__init__(self)
        self.layout = QGridLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(w1, 0, 0, 0, 1)
        self.layout.addWidget(w2, 0, 1, 0, 1)
        self.layout.addWidget(w3, 0, 2, 0, 1)
        self.setLayout(self.layout)


class Logic(QObject):
    update_status = pyqtSignal(str)
    update_progress = pyqtSignal(float)
    init_progress = pyqtSignal(float)
    analyze_finish_signal = pyqtSignal()
    filter_finish_signal = pyqtSignal(int, int)
    work_finish_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.stop_thread = False
        self.path = ""
        self.hashes = {}
        self.hash_table = {}
        self.paths_to_delete = []

    def reset(self):
        self.stop_thread = False
        self.path = ""
        self.hashes = {}
        self.hash_table = {}

    def work(self):
        self.update_status.emit("Starting moving")

        self.init_progress.emit(len(self.paths_to_delete))
        if not os.path.exists(os.path.join(self.path, "Cleanup")):
            os.mkdir(os.path.join(self.path, "Cleanup"))
        for i, folder in enumerate(self.paths_to_delete):
            src = os.path.join(self.path, "Songs", folder)
            dst = os.path.join(self.path, "Cleanup", folder)
            self.update_status.emit(f"moving folder: {folder}")
            try:
                shutil.move(src, dst)
            except Exception as e:
                print(e)
            self.update_progress.emit(i + 1)
        self.init_progress.emit(-1)
        self.update_status.emit("waiting for user action...")

        self.work_finish_signal.emit()

    def revert(self):
        self.update_status.emit("Reverting Cleanup")
        import glob
        files = glob.glob(os.path.join(self.path, "Cleanup", "*"))
        self.init_progress.emit(len(files))
        for i, src in enumerate(files):
            f = os.path.basename(src)
            dst = os.path.join(self.path, "Songs", f)
            self.update_status.emit(f"reverting folder: {f}")
            try:
                shutil.move(src, dst)
            except Exception as e:
                print(e)
            self.update_progress.emit(i + 1)
        shutil.rmtree(os.path.join(self.path, "Cleanup"))
        self.init_progress.emit(-1)
        self.update_status.emit("waiting for user action...")

    def filter(self, filters):
        assert filters
        self.update_status.emit("Filtering Beatmaps")
        self.init_progress.emit(0)
        paths = list(set(self.hash_table.values()))
        total_amount = len(paths)
        hashes_to_keep = [self.hashes[f] for f in filters]
        hashes_to_keep = list(chain.from_iterable(hashes_to_keep))
        hashes_to_keep = list(set(hashes_to_keep))

        self.init_progress.emit(len(hashes_to_keep))
        start = time.time()
        for i, h in enumerate(hashes_to_keep):
            if h in self.hash_table and self.hash_table[h] in paths:
                paths.remove(self.hash_table[h])
            now = time.time()
            if now - start >= 1 / 15:  # 15 fps update
                start = now
                self.update_progress.emit(i + 1)
        remove_amount = len(paths)
        self.paths_to_delete = paths
        self.filter_finish_signal.emit(total_amount, remove_amount)

        self.init_progress.emit(-1)
        self.update_status.emit("waiting for user action...")

    def analyze(self):
        self.update_status.emit("Copying Files to local tmp folder")
        self.init_progress.emit(0)
        files = ["osu!.db", "collection.db", "scores.db"]
        os.mkdir(os.path.abspath("tmp"))
        for file in files:
            shutil.copyfile(os.path.join(self.path, file), os.path.join(os.path.abspath("tmp"), file))

        self.update_status.emit("Loading Collections")
        cl_db = CollectionDb(os.path.abspath("tmp/collection.db"))

        self.update_status.emit("Processing Beatmaps in Collections")
        self.init_progress.emit(len(cl_db.collections))
        hashes = []
        for i, col in enumerate(cl_db.collections):
            if self.stop_thread:
                return
            hashes += list(set(col.hashes) - set(hashes))
            self.update_progress.emit(i + 1)
        self.hashes["collections"] = hashes
        self.init_progress.emit(-1)
        cl_db.inFile.close()
        del cl_db

        self.update_status.emit("Loading Beatmap with Scores")
        self.init_progress.emit(0)
        sc_db = ScoresDb(os.path.abspath("tmp/scores.db"))

        hashes = sc_db.scoresByHash.keys()
        self.hashes["scores"] = list(hashes)
        if self.stop_thread:
            return
        sc_db.inFile.close()
        del sc_db

        self.update_status.emit("Loading all Beatmaps")
        self.init_progress.emit(0)
        osu_db = SmallOsuDb(os.path.abspath("tmp/osu!.db"), self)

        self.update_status.emit("Processing all Beatmaps that have been played before")
        self.init_progress.emit(len(osu_db.beatmaps))
        hash_table = {}
        hashes = []
        start = time.time()
        for i, bm in enumerate(osu_db.beatmaps):
            if bm.directory not in osu_db.beatmaps:
                hash_table[bm.hash] = bm.directory
            if bm.lastPlayed != datetime.datetime(1, 1, 1):
                hashes.append(bm.hash)
            if self.stop_thread:
                return
            now = time.time()
            if now - start >= 1 / 15:  # 15 fps update
                start = now
                self.update_progress.emit(i + 1)

        self.hashes["played"] = hashes
        self.hash_table = hash_table
        self.init_progress.emit(-1)
        osu_db.inFile.close()
        del osu_db

        self.update_status.emit("Finished Scanning, deleting files")
        shutil.rmtree(os.path.abspath("tmp"))
        self.update_status.emit("waiting for user action...")
        self.init_progress.emit(-1)
        self.analyze_finish_signal.emit()
