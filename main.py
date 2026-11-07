import os
os.environ["QT_API"] = "pyside6"

from config import APP_NAME

os.environ["PULSE_PROP_application.name"] = APP_NAME
os.environ["PULSE_PROP_application.icon_name"] = "multimedia-audio-player"
os.environ["PULSE_PROP_media.role"] = "music"

if "QT_LOGGING_RULES" not in os.environ:
    os.environ["QT_LOGGING_RULES"] = "qt.multimedia.ffmpeg*=false;qt.multimedia*=false"
os.environ["AV_LOG_FORCE_NOCOLOR"] = "1"

from app import run

if __name__ == "__main__":
    run()