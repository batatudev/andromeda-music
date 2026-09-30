import os
os.environ["QT_API"] = "pyside6"
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtMultimedia import QMediaPlayer

app = QApplication(sys.argv)
player = QMediaPlayer()
print(dir(player))
