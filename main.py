import pygame
import tkinter as tk
from threading import Thread

from audio_lyrics_sync import AudioLyricsSync

if __name__ == "__main__":
    root = tk.Tk()
    app = AudioLyricsSync(root)
    root.mainloop()