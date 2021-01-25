from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtCore import Qt


def load_theme(app):
    accent = Qt.gray
    dark_p = QPalette()

    dark_p.setColor(QPalette.Window, QColor(12, 12, 12))
    dark_p.setColor(QPalette.WindowText, Qt.white)
    dark_p.setColor(QPalette.Base, QColor(25, 25, 25))
    dark_p.setColor(QPalette.AlternateBase, QColor(12, 12, 12))
    dark_p.setColor(QPalette.ToolTipBase, QColor(12, 12, 12))
    dark_p.setColor(QPalette.ToolTipText, Qt.white)
    dark_p.setColor(QPalette.Text, Qt.white)
    dark_p.setColor(QPalette.Button, QColor(12, 12, 12))
    dark_p.setColor(QPalette.ButtonText, Qt.white)
    dark_p.setColor(QPalette.BrightText, Qt.red)
    dark_p.setColor(QPalette.Highlight, accent)
    dark_p.setColor(QPalette.Inactive, QPalette.Highlight, Qt.lightGray)
    dark_p.setColor(QPalette.HighlightedText, Qt.black)
    dark_p.setColor(QPalette.Disabled, QPalette.Text, Qt.darkGray)
    dark_p.setColor(QPalette.Disabled, QPalette.ButtonText, Qt.darkGray)
    dark_p.setColor(QPalette.Disabled, QPalette.Highlight, Qt.darkGray)
    dark_p.setColor(QPalette.Disabled, QPalette.Base, QColor(25, 25, 25))
    dark_p.setColor(QPalette.Link, accent)
    dark_p.setColor(QPalette.LinkVisited, accent)

    app.setPalette(dark_p)
    app.setStyleSheet("""
            QToolTip {
                color: #ffffff;
                background-color: #2a2a2a;
                border: 1px solid white;
            }
            QLabel {
                    font-weight: Normal;
            }
            QTextEdit {
                    background-color: #212121;
            }
            LoadableW {
                    border: 1.5px solid #272727;
            }
            CheckW {
                    border: 1.5px solid #272727;
            }
            DragWidget {
                    border: 1.5px solid #272727;
            }""")