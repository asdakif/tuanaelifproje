# ─── Donanım Ayarları ──────────────────────────────────────────────────────────
BOX_PORT          = "COM4"  # Operant box seri port
TTL_PORT              = ""    # UltraSoundGate TTL portu (boş = simülasyon modu)
TTL_TRIGGER_DURATION_S = 0.01 # TTL pulse süresi (saniye)
AVISOFT_DOUT_PORT = ""      # Avisoft Player DOUT onay portu (boş = devre dışı)
CHANNEL           = 0x01    # Kutu kanal numarası (1-4)

# ─── Oturum Metadata ───────────────────────────────────────────────────────────
ANIMAL_ID = ""   # Her deney başında GUI'den girilir

# ─── Deney Parametreleri ───────────────────────────────────────────────────────
BASELINE_DURATION_S = 0.0  # Deney başlamadan önceki baseline süresi (saniye, 0 = devre dışı)
NUM_TRIALS        = 50     # Toplam trial sayısı
DS_PLUS_RATIO     = 0.5    # DS+ trial oranı (0.5 = %50)
ITI_MIN_S         = 5.0    # Minimum inter-trial interval (saniye)
ITI_MAX_S         = 10.0   # Maksimum inter-trial interval (saniye)
DS_DURATION_S     = 10.0   # DS cue süresi (saniye)
RESPONSE_WINDOW_S = 10.0   # Lever press bekleme süresi (saniye)
SHOCK_DURATION_S  = 0.5    # Şok süresi (saniye)
SHOCK_CURRENT_MA  = 0.2    # Şok akım şiddeti (mA) — 0.1 ile 0.4 arası

# ─── Outcome Ayarları ─────────────────────────────────────────────────────────
# Her DS tipi için lever basıldığında ne olacağını belirle.
# Seçenekler: "reward" (su) veya "punishment" (şok)
DS_PLUS_OUTCOME  = "reward"       # DS+ + lever press → ödül
DS_MINUS_OUTCOME = "punishment"   # DS− + lever press → ceza

# ─── Su Ödülü ─────────────────────────────────────────────────────────────────
WATER_SIDE        = 0x01   # 0x01 = sol, 0x02 = sağ
WATER_PULSES      = 3      # Her ödülde kaç pulse (damla)
WATER_PULSE_GAP_S = 0.1    # Pulse'lar arası bekleme (saniye)
LICK_WINDOW_S     = 10.0   # Ödülden sonra lick sayma süresi (saniye)

# ─── Lever Ayarları ────────────────────────────────────────────────────────────
LEVER_SIDE = 0x01         # 0x01 = sol, 0x02 = sağ
LEVER_EXTEND_ON_DS = True # True: DS başlayınca lever çıkar (False: response window'da çıkar)
RESPONSE_DELAY_S   = 0.0  # DS başladıktan kaç saniye sonra yanıt penceresi açılır (lever çıkar)

# ─── Işık Renkleri (R, G, B) ──────────────────────────────────────────────────
CUE_DS_PLUS_COLOR  = (0,   255, 0)    # DS+ → Yeşil
CUE_DS_MINUS_COLOR = (255, 0,   0)    # DS− → Kırmızı
HOUSE_LIGHT_COLOR  = (255, 255, 255)  # Beyaz (ITI sırasında)

# ─── Avisoft Playlist ─────────────────────────────────────────────────────────
DS_PLUS_WAV        = r"C:\sounds\ds_plus.wav"   # DS+ ses dosyası yolu
DS_MINUS_WAV       = r"C:\sounds\ds_minus.wav"  # DS− ses dosyası yolu
DS_PLUS_WAV_LIST   = []  # DS+ için birden fazla wav dosyası (boşsa DS_PLUS_WAV kullanılır)
DS_MINUS_WAV_LIST  = []  # DS− için birden fazla wav dosyası (boşsa DS_MINUS_WAV kullanılır)
AVISOFT_PLAYLIST   = r"C:\sounds\playlist.txt"  # Avisoft'un okuyacağı playlist
AVISOFT_EXE             = r"C:\Program Files (x86)\Avisoft Bioacoustics\RECORDER USGH\rec_usgh.exe"
AVISOFT_PLAYBACK_CONFIG = r"C:\Users\behne\Desktop\OC-USV\playback config\playback config.ini"
AVISOFT_RECORD_EXE        = ""                          # Bos birakilirsa Playback exe ile ayni kullanilir
AVISOFT_RECORD_CONFIG     = ""                          # Record config dosyasi
AVISOFT_RECORDER_WINDOW   = "Avisoft-RECORDER USGH #2"  # Recorder pencere basligi
AVISOFT_LAUNCH_DELAY_S  = 3.0   # Avisoft açıldıktan sonra deneyin başlaması için bekleme (saniye)

# ─── Avisoft BNC TTL Trigger ──────────────────────────────────────────────────
# DS sunumu başında operant kutu BNC çıkışından Avisoft'a TTL pulse gönderilir.
# Avisoft bu pulse'u trigger olarak alır ve ilgili sesi çalar.
# DS+ ve DS− farklı süre ile ayırt edilir.
BNC_DS_PLUS_VOLTAGE  = 3.3   # Volt (0.1 – 3.3)
BNC_DS_PLUS_DURATION = 100   # ms  → Avisoft "DS+ sesi" çalar

BNC_DS_MINUS_VOLTAGE  = 3.3  # Volt
BNC_DS_MINUS_DURATION = 200  # ms  → Avisoft "DS− sesi" çalar

# ─── Kriter Eşikleri ──────────────────────────────────────────────────────────
# Her trial sonunda hit_rate >= CRITERION_HIT_RATE VE d' >= CRITERION_DPRIME
# sağlanıyorsa CSV'de criterion_reached = 1 olarak işaretlenir.
CRITERION_HIT_RATE = 0.80   # Minimum hit rate (0.0–1.0)
CRITERION_DPRIME   = 1.5    # Minimum d' değeri

# ─── Log Klasörü ───────────────────────────────────────────────────────────────
LOG_DIR = "logs"
