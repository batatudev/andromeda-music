import sys
from PySide6.QtWidgets import QApplication, QPushButton, QWidget, QVBoxLayout

app = QApplication(sys.argv)
w = QWidget()
l = QVBoxLayout(w)

btn = QPushButton("Test")
l.addWidget(btn)

def make_cb(pid):
    return lambda: print("Clicked:", pid)

btn.clicked.connect(make_cb("test_id"))

btn.click()
