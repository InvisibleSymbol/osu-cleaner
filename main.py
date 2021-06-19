import os
import shutil
import threading
import time

import humanize
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (QLabel, QFrame, QPushButton, QMessageBox,
                             QVBoxLayout, QApplication, QMainWindow,
                             QLineEdit, QSizePolicy, QProgressBar)
from PyQt5.QtWinExtras import QWinTaskbarButton

import utils
from objects import FolderButton, MultiWidget, Logic, Filter, BottomWidget
from theme import load_theme

WINDOW_HEIGHT = 727
WINDOW_WIDTH = 420 + 48


class WindowWrapper(QMainWindow):

    def __init__(self):
        QMainWindow.__init__(self)
        self.main_window = MainWindow()
        self.main_window.taskbar_update_progress.connect(self.update_progress)
        self.main_window.taskbar_init_progress.connect(self.init_progress)
        self.setCentralWidget(self.main_window)
        self.setFixedWidth(WINDOW_HEIGHT)
        self.setFixedHeight(WINDOW_WIDTH)
        self.taskbar_button = QWinTaskbarButton()
        self.taskbar_progress = self.taskbar_button.progress()

    def showEvent(self, evt):
        self.taskbar_button.setWindow(self.windowHandle())

    def closeEvent(self, event):
        if self.main_window.thread.is_alive():
            quit_msg = "Seems like something is still running."
            reply = QMessageBox.warning(self, 'Are you sure you want to exit?',
                                        quit_msg, QMessageBox.Yes, QMessageBox.No)

            if reply == QMessageBox.Yes:
                event.accept()
            else:
                event.ignore()

    def update_progress(self, value):
        self.taskbar_progress.setValue(value)

    def init_progress(self, max_value):
        self.taskbar_progress.reset()
        if max_value == -1:
            self.taskbar_progress.hide()
        elif not self.taskbar_progress.isVisible():
            self.taskbar_progress.show()
        if max_value == 0:
            self.taskbar_progress.setMinimum(0)
            self.taskbar_progress.setMaximum(0)
        else:
            self.taskbar_progress.setRange(0, max_value)


class MainWindow(QFrame):
    taskbar_update_progress = pyqtSignal(float)
    taskbar_init_progress = pyqtSignal(float)

    def __init__(self):
        super().__init__()
        self.logic = Logic()

        self.thread = threading.Thread()
        self.thread.daemon = True

        self.info = QLabel(self)
        self.info.setTextFormat(Qt.RichText)
        self.info.setWordWrap(True)

        self.info.setText(
            '<h1 align="center">osu!cleaner</h1>'
            '<p align="center"><b>This is a really simple program that gives you the ability to quickly clean up your beatmap'
            ' folder.</b></p><p><hr><ul><li>'
            '<li>This will require you to do a rescan the next time you open osu!.<br>'
            '<li>To be safe the code doesn\'t directly touch any of osu!\'s databases and instead creates local copies.<br>'
            '<li>This doesn\'t delete the files itself either, it only moves them to a different folder called'
            ' "Cleanup" inside your osu! folder.'
            ' This is to prevent unintentionally deleting important maps.<hr><p align="center">'
            'I will try to automatically detect your osu! installation, but if it messes up please set the correct path bellow!'
            '</p>')
        self.info.setAlignment(Qt.AlignTop)
        self.info.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Maximum)
        self.header_filters = QLabel("What to keep:")
        self.header_filters.setContentsMargins(10, 10, 10, 0)
        self.filter_collections = Filter("Beatmaps in Collections", "collections")
        self.filter_scores = Filter("Beatmaps that have local Scores", "scores")
        self.filter_played = Filter("Beatmaps that have been played at least once locally", "played")
        self.filters = [self.filter_collections, self.filter_scores, self.filter_played]

        self.input_field = QLineEdit()
        self.input_field.setDisabled(True)

        self.folder_button = FolderButton("Select Folder")
        self.folder_button.path_chosen_signal.connect(self.validate_path)

        self.run_button = QPushButton("Run Cleanup")
        self.run_button.setDisabled(True)
        self.run_button.clicked.connect(self.ask_before_filter)

        self.revert_button = QPushButton("Revert Cleanup")
        self.revert_button.setDisabled(True)
        self.revert_button.clicked.connect(self.revert_cleanup)
        self.revert_button.setToolTip("Requires the initial Scan to be finished.")

        self.open_folder_button = QPushButton("Open Cleanup Folder")
        self.open_folder_button.setDisabled(True)
        self.open_folder_button.clicked.connect(self.open_cleanup_folder)

        self.delete_cleanup_button = QPushButton("Delete Cleanup Folder")
        self.delete_cleanup_button.setDisabled(True)
        self.delete_cleanup_button.clicked.connect(self.ask_before_deleting)

        self.container = MultiWidget(self.input_field, self.folder_button)

        self.progressbar = QProgressBar()
        self.progressbar.setFixedWidth(222 + 10)

        self.status_text = QLabel("waiting for user action...")
        self.status_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.sellout_text = QLabel('<code>- Made by InvisibleSymbol</code>')
        self.sellout_text = QLabel('<code> v1.0.1 - Made by InvisibleSymbol</code>')
        self.info.setTextFormat(Qt.RichText)
        self.sellout_text.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)

        self.layout = QVBoxLayout()
        self.layout.addWidget(self.info)
        self.layout.addWidget(self.container)
        self.layout.addWidget(self.header_filters)
        self.layout.addWidget(self.filter_collections)
        self.layout.addWidget(self.filter_scores)
        self.layout.addWidget(self.filter_played)
        self.layout.addWidget(self.filter_unsubmitted)
        self.layout.addWidget(self.run_button)
        self.layout.addWidget(MultiWidget(self.revert_button, self.open_folder_button, self.delete_cleanup_button))
        self.layout.addWidget(BottomWidget(self.progressbar, self.status_text, self.sellout_text))
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(self.layout)

        # signals
        self.logic.update_status.connect(self.update_status)
        self.logic.update_progress.connect(self.update_progress)
        self.logic.init_progress.connect(self.init_progress)

        self.logic.analyze_finish_signal.connect(self.post_process)
        self.logic.show_warning_signal.connect(self.show_warning)
        self.logic.filter_finish_signal.connect(self.return_from_filter)
        self.logic.work_finish_signal.connect(self.announce_finish)

        tmp = utils.get_osu_path()
        if tmp:
            self.validate_path(tmp)

    def init_progress(self, max_value):
        self.taskbar_init_progress.emit(max_value)
        if max_value == -1:
            self.progressbar.setRange(0, 1)
            self.progressbar.reset()
            return
        self.progressbar.setValue(0)
        self.progressbar.setRange(0, max_value)

    def open_cleanup_folder(self):
        os.startfile(os.path.join(self.logic.path, "Cleanup"))

    def ask_before_deleting(self):
        qm = QMessageBox()
        qm.setIcon(QMessageBox.Warning)
        qm.setWindowTitle("Are you sure about this?")
        qm.setText(f"This will delete all maps in the Cleanup folder!")
        qm.setInformativeText("No going back after this. Make sure you checked nothing important is missing.")
        qm.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        qm.setDefaultButton(QMessageBox.No)
        answer = qm.exec_()
        if answer == qm.Yes:
            shutil.rmtree(os.path.join(self.logic.path, "Cleanup"))
            self.delete_cleanup_button.setDisabled(True)
            self.open_folder_button.setDisabled(True)

    def show_warning(self, message):
        qm = QMessageBox()
        qm.setIcon(QMessageBox.Warning)
        qm.setWindowTitle("Error")
        qm.setText(f"An Error Occurred!")
        qm.setInformativeText(message)
        qm.setStandardButtons(QMessageBox.Ok)
        return qm.exec_()

    def update_progress(self, value):
        self.progressbar.setValue(value)
        self.taskbar_update_progress.emit(value)

    def update_status(self, string):
        self.status_text.setText(string[:64])

    def announce_finish(self):
        qm = QMessageBox()
        qm.setIcon(QMessageBox.Information)
        qm.setWindowTitle("Done c:")
        qm.setText(f"Your Filters have been successfully applied! Make sure to check the Result!")
        qm.setInformativeText("Start up osu! and do a full rescan by going to the Beatmap selection screen and pressing F5."
                              " If you are happy with the result you can press the \"Delete Cleanup Folder\" Button"
                              " to remove the Files, if not, press \"Revert Cleanup\" and all Files will be moved back.")
        qm.setStandardButtons(QMessageBox.Ok)
        self.run_button.setEnabled(True)
        self.folder_button.setEnabled(True)
        self.delete_cleanup_button.setEnabled(True)
        self.open_folder_button.setEnabled(True)
        self.revert_button.setEnabled(True)
        return qm.exec_()

    def post_process(self):
        for f in self.filters:
            cnt = len(self.logic.hashes[f.filter_name])
            f.update_hash_count(humanize.intcomma(cnt))
        self.run_button.setEnabled(True)
        if os.path.exists(os.path.join(self.logic.path, "Cleanup")):
            self.revert_button.setEnabled(True)

    def ask_before_filter(self):
        selected_filters = [f.filter_name for f in self.filters if f.toggle.checkState() == 2]

        # lets be safe...
        if not selected_filters:
            qm = QMessageBox()
            qm.setIcon(QMessageBox.Warning)
            qm.setWindowTitle("I'm sorry Dave, I'm afraid I can't do that.")
            qm.setText(f"Whoops. Seems like you didn't enable any filters. ")
            qm.setInformativeText("This would mean that all of your maps would get moved! "
                                  "To be safe this has been disabled c:")
            qm.setStandardButtons(QMessageBox.Abort | QMessageBox.Cancel | QMessageBox.Close)
            return qm.exec_()

        self.run_button.setDisabled(True)
        self.folder_button.setDisabled(True)
        self.thread = threading.Thread(target=self.logic.filter,
                                       name="osu!cleaner filter thread",
                                       args=(selected_filters,))
        self.thread.daemon = True
        self.thread.start()

    def revert_cleanup(self):
        self.thread = threading.Thread(target=self.logic.revert,
                                       name="osu!cleaner revert thread")
        self.thread.daemon = True
        self.thread.start()
        self.revert_button.setDisabled(True)
        self.open_folder_button.setDisabled(True)
        self.delete_cleanup_button.setDisabled(True)

    def return_from_filter(self, total_count, remove_amount):
        qm = QMessageBox()
        qm.setIcon(QMessageBox.Warning)
        qm.setWindowTitle("Are you sure about this?")
        qm.setText(f"This will move {remove_amount} Beatmaps, "
                   f"which will result in a new total of {total_count - remove_amount} Beatmaps!")
        qm.setInformativeText("Please note that this doesn\'t delete the files itself. "
                              "It is your job to click the delete button after you have confirmed that no important maps are missing.")
        qm.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        qm.setDefaultButton(QMessageBox.No)
        answer = qm.exec_()
        if answer == qm.Yes:
            self.thread = threading.Thread(target=self.logic.work,
                                           name="osu!cleaner work thread")
            self.thread.daemon = True
            self.thread.start()
        else:
            self.run_button.setEnabled(True)
            self.folder_button.setEnabled(True)

    def validate_path(self, path):
        if os.path.exists(os.path.join(path, "Cleanup")):
            self.delete_cleanup_button.setEnabled(True)
            self.open_folder_button.setEnabled(True)
        self.folder_button.setDisabled(True)
        self.run_button.setDisabled(True)
        self.logic.stop_thread = True
        while self.thread.is_alive():
            self.update_status("Killing Logic Thread...")
            time.sleep(1 / 15)  # 15fps
            QApplication.processEvents()
        self.clean_up()
        self.input_field.setText(str(path))
        files = ["osu!.exe", "osu!.db", "collection.db", "scores.db", "Songs"]
        if all(os.path.exists(os.path.join(path, file)) for file in files):
            self.update_status("Path looks fine, starting scan...")
            self.logic.path = path
            self.thread.start()
        else:
            self.update_status("Path seems to be incorrect")
        self.folder_button.setDisabled(False)

    def clean_up(self):
        self.init_progress(-1)
        for f in self.filters:
            f.update_hash_count("???")
        self.logic.reset()
        self.thread = threading.Thread(target=self.logic.analyze, name="osu!cleaner analyze thread")
        self.thread.daemon = True
        try:
            shutil.rmtree(os.path.abspath("tmp"))
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    # app setup
    app = QApplication([])
    app.setStyle("Fusion")
    app.setApplicationName("osu!cleaner")
    app.setWindowIcon(QIcon("res/icon.ico"))
    # load theme
    load_theme(app)
    # window
    WINDOW = WindowWrapper()
    WINDOW.show()
    app.exec_()
