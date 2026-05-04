from config import *

GROUP = "congruent"
DS_PLUS_WAV  = r"C:\sounds\50kHz_DS_plus.wav"   # 50 kHz → Go / reward
DS_MINUS_WAV = r"C:\sounds\22kHz_DS_minus.wav"  # 22 kHz → No-Go / punishment
AVISOFT_PLAYLIST = r"C:\sounds\playlist_congruent.txt"

# Reversal'da roller değişir (experiment.reversal_mode=True ile aktif edilir)
# Reversal DS+ = 22 kHz, DS- = 50 kHz — WAV dosyaları aynı kalır,
# experiment.py reversal_mode flag'iyle hangi sesin Go olduğunu bilir.
