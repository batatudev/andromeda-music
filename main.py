import os
os.environ["QT_API"] = "pyside6"

from config import APP_NAME

os.environ["PULSE_PROP_application.name"] = APP_NAME
os.environ["PULSE_PROP_application.icon_name"] = "multimedia-audio-player"
os.environ["PULSE_PROP_media.role"] = "music"

from app import run

if __name__ == "__main__":
    run()