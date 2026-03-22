# Operant Koşullanma Deney Yazılımı

**DS+/DS− Discriminative Stimulus Paradigm Controller**
Boğaziçi Üniversitesi — Davranışsal Nörobilim Laboratuvarı

---

## İçindekiler

- [Genel Bakış](#genel-bakış)
- [Donanım Gereksinimleri](#donanım-gereksinimleri)
- [Yazılım Gereksinimleri](#yazılım-gereksinimleri)
- [Kurulum](#kurulum)
- [Hızlı Başlangıç](#hızlı-başlangıç)
- [Avisoft Ayarları](#avisoft-ayarları)
- [Parametreler ve Konfigürasyon](#parametreler-ve-konfigürasyon)
- [Deney Protokolü](#deney-protokolü)
- [Veri Çıktısı (CSV)](#veri-çıktısı-csv)
- [Simülasyon Modu](#simülasyon-modu)
- [Sistem Diyagramları](#sistem-diyagramları)
- [Klasör Yapısı](#klasör-yapısı)

---

## Genel Bakış

Bu yazılım, Conduct Science operant kutusu ile **DS+/DS− diskriminatif stimulus** paradigması üzerinden **operant koşullanma** deneyleri yürütmek için geliştirilmiştir.

**Temel mantık:**
- **DS+** sesi/ışığı aktifken hayvan levere basarsa → **Ödül** (su) veya **Ceza** (şok) *(konfigüre edilebilir)*
- **DS−** sesi/ışığı aktifken hayvan levere **basmazsa** → **Correct Rejection** (doğru yanıt)
- **DS−** aktifken yanlışlıkla basarsa → **False Alarm** (yanlış alarm)
- **DS+** aktifken basmayı kaçırırsa → **Omission** (hata)

Yazılım her oturumun sonunda **Hit Rate**, **Correct Rejection Rate** ve **d' (d-prime)** istatistiklerini hesaplar ve canlı olarak gösterir.

### Desteklenen Özellikler

| Özellik | Detay |
|---|---|
| Lever seçimi | Sol (0x01) veya Sağ (0x02) — GUI'den |
| DS+ Outcome | Ödül (su) veya Ceza (şok) — konfigüre edilebilir |
| DS− Outcome | Ödül (su) veya Ceza (şok) — konfigüre edilebilir |
| Ultrasonik ses | Avisoft Player 116H + BNC TTL trigger |
| Şok akımı | 0.1 – 0.4 mA, ayarlanabilir |
| Su ödülü | Pulse sayısı ve aralığı ayarlanabilir |
| Lick sayımı | Ödül sonrası lick penceresi (lickometre) |
| ITI lever press | Dürtüsellik ölçümü (anticipatory press sayımı) |
| Dual RT | DS başlangıcından ve lever uzayışından tepki süresi |
| Live metrikler | Hit Rate / CR Rate / d' her trial sonunda güncellenir |
| Simülasyon modu | Donanım olmadan tam test |
| CSV loglama | Hayvan ID dahil tüm parametreler kaydedilir |

---

## Donanım Gereksinimleri

```
Bilgisayar (Windows)
│
├── COM3 ──── Conduct Science Operant Kutu (115200 baud, 8N1)
│                ├── Sol Lever (0x01)
│                ├── Sağ Lever (0x02)
│                ├── Su Dispenseri + Lickometre
│                ├── Şok Jeneratörü (0.1–0.4 mA)
│                ├── Cue Light RGB (sol / sağ)
│                ├── House Light RGB
│                └── BNC TTL Çıkışı ──── Avisoft Player 116H TRG Girişi
│
└── USB ──── Avisoft UltraSoundGate Player 116H
                 └── LINE OUT ─── Amplifikatör ─── Ultrasonik Hoparlör
```

> **Not:** Arduino veya ek donanım gerekmez. Tek BNC kablo: Operant Kutu BNC çıkışı → Avisoft TRG girişi.

### Minimum Donanım Listesi

- Conduct Science Operant Kutu (rat için)
- Avisoft Bioacoustics UltraSoundGate Player 116H
- BNC kablo (kutu BNC çıkışı → Avisoft TRG)
- Ultrasonik hoparlör + amplifikatör
- Windows bilgisayar (COM port ile)

---

## Yazılım Gereksinimleri

- **Python 3.9+** (tkinter dahil)
- **pyserial** — seri port iletişimi
- **openpyxl** — (opsiyonel, API referans dosyası için)

### Kurulum

```bash
# Depoyu klonla
git clone https://github.com/asdakif/tuanaelifproje.git
cd tuanaelifproje

# Bağımlılıkları yükle
pip install pyserial openpyxl

# macOS'ta tkinter için (gerekirse)
brew install python-tk@3.14
```

---

## Hızlı Başlangıç

```bash
python main.py
```

1. **Hayvan ID** girin (zorunlu — CSV dosya adına ve her satıra eklenir)
2. **Seri Port** girin (örn. `COM3`). Boş bırakırsanız simülasyon modunda çalışır.
3. **Parametreleri** ayarlayın (trial sayısı, ITI, DS süresi, şok, su, vb.)
4. **Lever** ve **Outcome** ayarlarını seçin
5. **▶ Başlat** tuşuna basın
6. Avisoft'ta `playlist.txt` dosyasını açın (bkz. [Avisoft Ayarları](#avisoft-ayarları))
7. Oturum tamamlandığında popup ile sonuçlar gösterilir

### GUI Ekranı

```
┌─────────────────────────────────────┬─────────────────────────────────┐
│  OTURUM BİLGİSİ                     │  DS Gösterge (Yeşil/Kırmızı)   │
│  Hayvan ID: [RAT_01]                │                                 │
│  Port: [COM3]                       │  TRIAL SONUÇLARI               │
│                                     │  Rewarded:         0            │
│  DENEY PARAMETRELERİ                │  Punished:         0            │
│  Trial: [50]  DS+ Oran: [0.5]       │  Omission:         0            │
│  ITI: [5] – [10] sn                 │  Correct Rejection: 0           │
│  DS Süresi: [10] sn                 │                                 │
│  Yanıt Penceresi: [10] sn           │  DİSKRİMİNASYON                │
│  Şok: [0.5]sn  [0.2]mA             │  Hit Rate:  —%                  │
│  Max Üst üste: [3]                  │  CR Rate:   —%                  │
│                                     │  d':        —                   │
│  LEVER AYARLARI                     │  [████████░░░░░░░░░░]           │
│  Lever: [Sol ▼]                     │                                 │
│  DS'de lever çık: [✓]               │  Toplam Lick: 0                 │
│                                     │  ITI Press:  0                  │
│  OUTCOME AYARLARI                   │                                 │
│  DS+ Outcome: [Ödül ▼]             │  LOG                            │
│  DS− Outcome: [Ceza ▼]             │  > Oturum başlatıldı...         │
│  Su Pulsleri: [3]                   │  > Trial 1: DS+ ...             │
│                                     │                                 │
│  [▶ Başlat]  [⏹ Durdur]           │                                 │
└─────────────────────────────────────┴─────────────────────────────────┘
```

---

## Avisoft Ayarları

Her oturum başında yazılım otomatik olarak bir `playlist.txt` dosyası üretir. Bu dosya, trial sırasına göre `ds_plus.wav` ve `ds_minus.wav` dosyalarını listeler.

### Adımlar

1. **`config.py`'da ses dosyası yollarını ayarla:**
   ```python
   DS_PLUS_WAV      = r"C:\sounds\ds_plus.wav"
   DS_MINUS_WAV     = r"C:\sounds\ds_minus.wav"
   AVISOFT_PLAYLIST = r"C:\sounds\playlist.txt"
   ```

2. **Avisoft yazılımında:**
   - `File` → `Open` → `playlist.txt` dosyasını seç
   - **"Stop after each file"** seçeneğini işaretle ✓
   - Yazılımı hazır beklet

3. **Deney çalışınca:**
   - Her DS sunumunda operant kutu BNC çıkışından TTL pulse gönderilir
   - Avisoft bu pulse'u alır ve sıradaki ses dosyasını çalar
   - DS+ → 100ms TTL → `ds_plus.wav`
   - DS− → 200ms TTL → `ds_minus.wav`

> **Önemli:** Avisoft DOUT onay portu opsiyoneldir. GUI'de DOUT Port alanını boş bırakırsanız devre dışı kalır.

---

## Parametreler ve Konfigürasyon

Tüm parametreler hem `config.py` dosyasında hem de GUI'den ayarlanabilir. Kod değiştirmeye gerek yoktur.

### `config.py` Referansı

| Parametre | Varsayılan | Açıklama |
|---|---|---|
| `BOX_PORT` | `"COM3"` | Operant kutu seri portu |
| `AVISOFT_DOUT_PORT` | `""` | Avisoft ses onay portu (boş = devre dışı) |
| `NUM_TRIALS` | `50` | Toplam trial sayısı |
| `DS_PLUS_RATIO` | `0.5` | DS+ trial oranı (0.0–1.0) |
| `ITI_MIN_S` | `5.0` | Minimum ITI (saniye) |
| `ITI_MAX_S` | `10.0` | Maksimum ITI (saniye) |
| `DS_DURATION_S` | `10.0` | DS cue süresi (saniye) |
| `RESPONSE_WINDOW_S` | `10.0` | Yanıt penceresi (saniye) |
| `SHOCK_DURATION_S` | `0.5` | Şok süresi (saniye) |
| `SHOCK_CURRENT_MA` | `0.2` | Şok akımı (0.1–0.4 mA) |
| `DS_PLUS_OUTCOME` | `"reward"` | DS+ basınca: `"reward"` veya `"punishment"` |
| `DS_MINUS_OUTCOME` | `"punishment"` | DS− basınca: `"reward"` veya `"punishment"` |
| `WATER_PULSES` | `3` | Su pulse sayısı |
| `WATER_PULSE_GAP_S` | `0.1` | Pulse arası bekleme (saniye) |
| `LICK_WINDOW_S` | `10.0` | Lick sayma penceresi (saniye) |
| `LEVER_SIDE` | `0x01` | `0x01` = Sol, `0x02` = Sağ |
| `LEVER_EXTEND_ON_DS` | `True` | `True`: lever DS başlayınca çıkar |
| `BNC_DS_PLUS_DURATION` | `100` | DS+ TTL süresi (ms) |
| `BNC_DS_MINUS_DURATION` | `200` | DS− TTL süresi (ms) |

---

## Deney Protokolü

### Trial Sırası Üretimi

- Trial sırası **dengeli rastgele** üretilir (belirli DS+ oranı korunur)
- **Maksimum üst üste kısıtı:** Aynı DS tipi art arda en fazla N kez gelir (GUI'den ayarlanır, varsayılan 3)

### Tek Trial Akışı

```
ITI (5–10 sn, rastgele)
  ├── House light AÇIK (beyaz)
  ├── Lever İÇERİDE
  └── ITI lever press → iti_presses++ (dürtüsellik ölçümü)
       ↓
DS Sunumu
  ├── DS+: Cue light YEŞİL + BNC TTL 100ms + ds_plus.wav
  └── DS−: Cue light KIRMIZI + BNC TTL 200ms + ds_minus.wav
       ↓
Lever Uzar (LEVER_EXTEND_ON_DS=True: DS başlayınca; False: yanıt penceresinde)
       ↓
Yanıt Penceresi (10 sn)
  ├── Lever basıldı + DS+ → Outcome (ödül/ceza)
  ├── Lever basıldı + DS− → Outcome (ödül/ceza)
  ├── Süre doldu + DS+ → OMISSION (hata)
  └── Süre doldu + DS− → CORRECT REJECTION (doğru)
       ↓
Outcome
  ├── Ödül: Su dispenseri → Lick penceresi (lick_count sayılır)
  └── Ceza: Şok (ayarlanabilir mA, ayarlanabilir süre)
       ↓
CSV'ye kaydet + diskriminasyon güncelle → Sonraki ITI
```

### Diskriminasyon Metrikleri

| Metrik | Formül |
|---|---|
| **Hit Rate** | DS+ triallarda basış sayısı / Toplam DS+ trial |
| **CR Rate** | DS− triallarda basılmayan / Toplam DS− trial |
| **d' (d-prime)** | Z(Hit Rate) − Z(False Alarm Rate) |

d' hesabı için Z fonksiyonu rational approximation (probit) ile scipy kullanmadan uygulanmıştır.

---

## Veri Çıktısı (CSV)

Her oturum `logs/` klasörüne otomatik kaydedilir:

**Dosya adı formatı:** `session_<AnimalID>_<YYYYMMDD>_<HHMMSS>.csv`

### CSV Sütunları

| Sütun | Açıklama |
|---|---|
| `animal_id` | Hayvan ID (zorunlu) |
| `trial` | Trial numarası (1'den başlar) |
| `ds_type` | `DS+` veya `DS-` |
| `result` | `rewarded`, `punished`, `omission`, `correct_rejection` |
| `rt_from_ds_s` | DS başlangıcından lever basışına süre (saniye) |
| `rt_from_lever_s` | Lever uzayışından basışa süre (saniye) |
| `lick_count` | Ödül sonrası toplam lick sayısı |
| `iti_presses` | Bu trialdaki ITI lever press sayısı |
| `hit_rate` | Kümülatif hit oranı (%) |
| `cr_rate` | Kümülatif correct rejection oranı (%) |
| `d_prime` | Kümülatif d' değeri |
| `rewarded` | Ödüllü trial sayısı (kümülatif) |
| `punished` | Cezalı trial sayısı (kümülatif) |
| `omission` | Omission sayısı (kümülatif) |
| `correct_rejection` | Correct rejection sayısı (kümülatif) |
| `timestamp` | ISO 8601 zaman damgası |

### Örnek CSV Satırı

```
animal_id,trial,ds_type,result,rt_from_ds_s,rt_from_lever_s,lick_count,iti_presses,hit_rate,cr_rate,d_prime,...
RAT_01,1,DS+,rewarded,12.34,2.34,8,0,100.0,,,1
RAT_01,2,DS-,correct_rejection,,,0,0,100.0,100.0,4.65,1,0,0,2
```

---

## Simülasyon Modu

Donanım olmadan yazılımı test etmek için:

1. GUI'de **Port alanını boş bırak**
2. `▶ Başlat`'a bas
3. Sol paneldeki **Simülasyon** butonlarını kullan:
   - **Lever Press (Sim)** — lever basışı simüle eder
   - **Lick (Sim)** — lick eventi simüle eder

Tüm state machine, CSV loglama ve diskriminasyon metrikleri simülasyon modunda da tam çalışır.

---

## Sistem Diyagramları

`diagrams/` klasöründe PlantUML kaynak dosyaları bulunur. [plantuml.com](https://plantuml.com) veya VS Code PlantUML eklentisi ile PNG'ye çevirebilirsiniz.

| Dosya | İçerik |
|---|---|
| `01_system_architecture.puml` | Donanım mimarisi ve bağlantı şeması |
| `02_trial_flow.puml` | Tek trial akış diyagramı (swimlane) |
| `03_state_machine.puml` | Deney state machine (tüm durumlar ve geçişler) |
| `04_sequence_diagram.puml` | Tam oturum sequence diyagramı |

---

## Klasör Yapısı

```
tuanaelifproje/
│
├── main.py              # GUI (Tkinter) — giriş noktası
├── experiment.py        # Deney state machine
├── operant_box.py       # Seri port iletişim katmanı (Conduct Science API)
├── ttl_listener.py      # Avisoft TTL listener (opsiyonel)
├── config.py            # Tüm parametreler
│
├── diagrams/
│   ├── 01_system_architecture.puml
│   ├── 02_trial_flow.puml
│   ├── 03_state_machine.puml
│   └── 04_sequence_diagram.puml
│
└── logs/
    └── session_<AnimalID>_<tarih>_<saat>.csv
```

---

## Teknik Notlar

### Conduct Science Seri Protokolü

Paket formatı: `0xAA 0xBB [channel] [type] [data...] 0xCC 0xDD`
- Baud rate: 115200, 8N1
- Kanal: `0x01` (varsayılan)

### BNC TTL Trigger Mantığı

- DS+ sunumunda: 3.3V / 100ms pulse → Avisoft DS+ sesini çalar
- DS− sunumunda: 3.3V / 200ms pulse → Avisoft DS− sesini çalar
- Avisoft "stop after each file" modunda çalışır — her pulse sıradaki dosyayı çalar

### Lick Olayı

Lickometre olayı `0xA3 0x02` paketi olarak gelir. Yazılım, ödül sonrası `LICK_WINDOW_S` saniye boyunca lick sayar.

