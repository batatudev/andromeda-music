import os
os.environ["QT_API"] = "pyside6"

# WERSJA PROJEKTU: 14.20
# MODYFIKOWANY PLIK: engine/queue_manager.py
# OPIS ZMIAN: Naprawa logiki Drag & Drop (handle_drop) oraz bezpieczne śledzenie aktywnego utworu

import random
from PySide6.QtCore import QObject, Signal

class QueueManager(QObject):
    """
    Dedykowany menedżer kolejki odtwarzania.
    Zarządza listą utworów, aktywnym indeksem oraz trybami losowania i pętli.
    """
    queue_updated = Signal()
    queue_cleared = Signal()
    loop_mode_changed = Signal(bool)
    shuffle_mode_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.queue = []
        self.idx = -1
        self.is_looping = False
        self.is_shuffled = False

    def current_song(self):
        if 0 <= self.idx < len(self.queue):
            return self.queue[self.idx]
        return None

    def has_current(self):
        return 0 <= self.idx < len(self.queue)

    def next_song_item(self):
        if 0 <= self.idx and (self.idx + 1) < len(self.queue):
            return self.queue[self.idx + 1]
        return None

    def set_queue(self, songs, start_idx=0):
        self.queue = list(songs)
        self.idx = start_idx
        self.queue_updated.emit()

    def add(self, song):
        self.queue.append(song)
        self.queue_updated.emit()

    def clear(self):
        self.queue = []
        self.idx = -1
        self.queue_cleared.emit()

    def shuffle(self, new_songs=None):
        if new_songs:
            self.set_queue(new_songs, 0)
            return

        if len(self.queue) > 1 and 0 <= self.idx < len(self.queue):
            current_song = self.queue[self.idx]
            q_copy = self.queue[:]
            q_copy.pop(self.idx)
            random.shuffle(q_copy)
            self.queue = [current_song] + q_copy
            self.idx = 0
            self.queue_updated.emit()

    def handle_drop(self, old_idx, target_q_idx):
        if not (0 <= old_idx < len(self.queue)):
            return
        if target_q_idx == old_idx or target_q_idx == old_idx + 1:
            return

        current_playing = self.current_song()
        song = self.queue.pop(old_idx)

        if old_idx < target_q_idx:
            target_q_idx -= 1

        self.queue.insert(target_q_idx, song)

        if current_playing and current_playing in self.queue:
            self.idx = self.queue.index(current_playing)

        self.queue_updated.emit()

    def play_next(self, index):
        if self.idx < 0:
            target_idx = 0
        else:
            target_idx = self.idx + 1
        if index == target_idx or index == self.idx:
            return
        song = self.queue.pop(index)
        if index < target_idx:
            target_idx -= 1
        self.queue.insert(target_idx, song)
        if self.idx == index:
            self.idx = target_idx
        elif index < self.idx <= target_idx:
            self.idx -= 1
        elif target_idx <= self.idx < index:
            self.idx += 1
        self.queue_updated.emit()

    def remove(self, index):
        """
        Usuwa utwór z kolejki.
        Zwraca krotkę (should_play_current, should_clear):
        - (True, False): usunięto grający utwór i należy załadować kolejny
        - (False, True): usunięto ostatni utwór i kolejka jest pusta
        - (False, False): usunięto utwór w tle bez wpływu na aktualne odtwarzanie
        """
        if not (0 <= index < len(self.queue)):
            return False, False

        if index < self.idx:
            self.queue.pop(index)
            self.idx -= 1
            self.queue_updated.emit()
            return False, False
        elif index == self.idx:
            self.queue.pop(index)
            if len(self.queue) == 0:
                self.clear()
                return False, True
            else:
                if self.idx >= len(self.queue):
                    self.clear()
                    return False, True
                else:
                    self.queue_updated.emit()
                    return True, False
        else:
            self.queue.pop(index)
            self.queue_updated.emit()
            return False, False

    def advance(self):
        """Przesuwa indeks do przodu. Zwraca True, jeśli utwór istnieje."""
        if self.idx < len(self.queue) - 1:
            self.idx += 1
            return True
        return False

    def previous(self):
        """Cofa indeks o 1. Zwraca True, jeśli utwór istnieje."""
        if self.idx > 0:
            self.idx -= 1
            return True
        return False

    def set_loop(self, state):
        if self.is_looping != state:
            self.is_looping = state
            self.loop_mode_changed.emit(self.is_looping)

    def toggle_loop(self):
        self.set_loop(not self.is_looping)
        return self.is_looping

    def set_shuffle(self, state):
        if self.is_shuffled != state:
            self.is_shuffled = state
            if self.is_shuffled:
                self.shuffle()
            self.shuffle_mode_changed.emit(self.is_shuffled)

    def toggle_shuffle(self):
        self.set_shuffle(not self.is_shuffled)
        return self.is_shuffled