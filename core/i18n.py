import os
import json
from PySide6.QtCore import QObject, Signal
from config import APP_CONFIG

class Translator(QObject):
    language_changed = Signal(str)

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Translator, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized: return
        super().__init__()
        self._initialized = True
        self.current_lang = APP_CONFIG.get("language", "pl")
        self.dict = {}
        self.load_language(self.current_lang)

    def load_language(self, lang_code: str):
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "lang", f"{lang_code}.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.dict = json.load(f)
                self.current_lang = lang_code
            except Exception as e:
                print(f"Error loading translation: {e}")
                self.dict = {}
        else:
            self.dict = {}
            self.current_lang = lang_code
        self.language_changed.emit(self.current_lang)

    def t(self, key: str, default: str = None) -> str:
        """Tłumaczy dany klucz na bieżący język."""
        return self.dict.get(key, default if default is not None else key)

    def set_language(self, lang_code: str):
        self.load_language(lang_code)
        APP_CONFIG["language"] = lang_code
        from config import save_config
        save_config()

_translator = Translator()

def tr(key: str, default: str = None) -> str:
    return _translator.t(key, default)
