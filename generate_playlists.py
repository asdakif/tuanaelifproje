"""
Haftalık Avisoft Playlist Üretici
Her grup (congruent, incongruent, control) için 5 günlük playlist dosyası üretir.
"""

import os
import random
import math

OUTPUT_DIR = os.path.join(os.path.expanduser("~"), "Desktop", "haftalik_playlistler")

_GROUPS = {
    "congruent": {
        "ds_plus_wav":       r"C:\sounds\50kHz_DS_plus.wav",
        "ds_minus_wav":      r"C:\sounds\22kHz_DS_minus.wav",
        # Birden fazla dosya için listeye ekle (boşsa yukarıdaki tek dosya kullanılır):
        "ds_plus_wav_list":  [],  # örn: [r"C:\sounds\50kHz_1.wav", r"C:\sounds\50kHz_2.wav"]
        "ds_minus_wav_list": [],  # örn: [r"C:\sounds\22kHz_1.wav", r"C:\sounds\22kHz_2.wav"]
    },
    "incongruent": {
        "ds_plus_wav":       r"C:\sounds\22kHz_DS_plus.wav",
        "ds_minus_wav":      r"C:\sounds\50kHz_DS_minus.wav",
        "ds_plus_wav_list":  [],
        "ds_minus_wav_list": [],
    },
    "control": {
        "ds_plus_wav":       r"C:\sounds\tone_2kHz_DS_plus.wav",
        "ds_minus_wav":      r"C:\sounds\tone_8kHz_DS_minus.wav",
        "ds_plus_wav_list":  [],
        "ds_minus_wav_list": [],
    },
}

NUM_TRIALS      = 50
DS_PLUS_RATIO   = 0.5
MAX_CONSECUTIVE = 3
DAYS_PER_WEEK   = 5


def _make_sequence(num_trials: int, ratio: float, max_consec: int) -> list:
    n_plus  = round(num_trials * ratio)
    n_minus = num_trials - n_plus
    seq     = ["DS+"] * n_plus + ["DS-"] * n_minus

    for _ in range(10_000):
        random.shuffle(seq)
        ok    = True
        count = 1
        for i in range(1, len(seq)):
            if seq[i] == seq[i - 1]:
                count += 1
                if count > max_consec:
                    ok = False
                    break
            else:
                count = 1
        if ok:
            return seq

    return seq


def _make_playlist_lines(seq: list, ds_plus_wav: str, ds_minus_wav: str,
                          ds_plus_wav_list: list = None,
                          ds_minus_wav_list: list = None) -> list:
    plus_pool  = ds_plus_wav_list  if ds_plus_wav_list  else [ds_plus_wav]
    minus_pool = ds_minus_wav_list if ds_minus_wav_list else [ds_minus_wav]
    return [random.choice(plus_pool) if ds == "DS+" else random.choice(minus_pool)
            for ds in seq]


def generate_all():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for group, wavs in _GROUPS.items():
        group_dir = os.path.join(OUTPUT_DIR, group)
        os.makedirs(group_dir, exist_ok=True)

        for day in range(1, DAYS_PER_WEEK + 1):
            seq   = _make_sequence(NUM_TRIALS, DS_PLUS_RATIO, MAX_CONSECUTIVE)
            lines = _make_playlist_lines(
                seq,
                wavs["ds_plus_wav"],
                wavs["ds_minus_wav"],
                wavs.get("ds_plus_wav_list"),
                wavs.get("ds_minus_wav_list"),
            )
            path  = os.path.join(group_dir, f"playlist_gun{day}.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
