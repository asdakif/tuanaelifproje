# Operant Koşullanma Deney Yazılımı

**DS+/DS− Discriminative Stimulus Paradigm Controller**
Boğaziçi Üniversitesi — Davranışsal Nörobilim Laboratuvarı

---

## İçindekiler

- [Genel Bakış](#genel-bakış)
- [Donanım Gereksinimleri](#donanım-gereksinimleri)
- [Kurulum](#kurulum)
- [Hızlı Başlangıç](#hızlı-başlangıç)
- [Çoklu Hayvan Oturumu](#çoklu-hayvan-oturumu)
- [Donanım Testi](#donanım-testi)
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

Her oturumun sonunda **Hit Rate**, **Correct Rejection Rate** ve **d' (d-prime)** istatistikleri hesaplanır ve canlı olarak gösterilir.

### Desteklenen Özellikler

| Özellik | Detay |
|---|---|
| Çoklu hayvan | Oturum başında liste gir, hayvanlar sırayla otomatik çalışır |
| Lever seçimi | Sol (0x01) veya Sağ (0x02) — GUI'den |
| Su tarafı | Lever tarafıyla otomatik eşlenir, manuel değiştirilebilir |
| DS+ Outcome | Ödül (su) veya Ceza (şok) — konfigüre edilebilir |
| DS− Outcome | Ödül (su) veya Ceza (şok) — konfigüre edilebilir |
| Ultrasonik ses | Avisoft Player 116H + BNC TTL trigger |
| Şok akımı | 0.1 – 0.4 mA, ayarlanabilir |
| Su ödülü | Pulse sayısı ve aralığı ayarlanabilir |
| Lick sayımı | Ödül sonrası lick penceresi (lickometre) |
| ITI lever press | Dürtüsellik ölçümü (anticipatory press sayımı) |
| Dual RT | DS başlangıcından ve lever uzayışından tepki süresi |
| Live metrikler | Hit Rate / CR Rate / d' her trial sonunda güncellenir |
| Donanım testi | Deney öncesi her bileşeni tek tek test et |
| Avisoft sync log | DOUT miss → CRITICAL log + CSV'de `sound_confirmed` kolonu |
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

## Kurulum

```bash
# Depoyu klonla
git clone https://github.com/asdakif/tuanaelifproje.git
cd tuanaelifproje

# Bağımlılıkları yükle
pip install -r requirements.txt

# macOS'ta tkinter için (gerekirse)
brew install python-tk@3.14
```

---

## Hızlı Başlangıç

```bash
python main.py
```

1. **Hayvan Listesi**'ne ID'leri girin (her satıra bir tane)
2. **Kutu Portu** girin (örn. `COM3`). Boş = simülasyon modu
3. **Parametreleri** ayarlayın
4. **Lever** ve **Outcome** ayarlarını seçin
5. **Bağlan**'a basın
6. **Donanım Testi** ile bileşenleri doğrulayın *(önerilir)*
7. **▶ Başlat**'a basın → `playlist.txt` otomatik üretilir
8. Avisoft'ta `playlist.txt` dosyasını açın (bkz. [Avisoft Ayarları](#avisoft-ayarları))

### GUI Düzeni

```
┌─────────────────────────────────────┬─────────────────────────────────┐
│  OTURUM BİLGİSİ          (scroll)  │  DS Gösterge (Yeşil/Kırmızı)   │
│  Hayvan Listesi:                    │  Durum: ITI                     │
│  ┌──────────────┐                  │  Trial: 3 / 50                  │
│  │ RAT_01       │  Sıra: 1/4       │                                 │
│  │ RAT_02       │  Şu an: RAT_01   │  TRIAL SONUÇLARI               │
│  │ RAT_03       │                  │  Rewarded:          12          │
│  │ RAT_04       │                  │  Punished:           0          │
│  └──────────────┘                  │  Omission:           3          │
│                                     │  Correct Rejection: 10          │
│  BAĞLANTI AYARLARI                 │                                 │
│  Kutu Portu: [COM3]                │  DİSKRİMİNASYON                │
│  TTL Portu:  [   ]                 │  Hit Rate:  80.0%               │
│  [✓] Simülasyon modu               │  CR Rate:   76.9%               │
│  [Bağlan]                          │  d':        1.42                │
│                                     │  [████████████░░░░░░]           │
│  DENEY PARAMETRELERİ               │                                 │
│  Trial: [50]  DS+ Oran: [0.5]      │  Lick (bu trial): 5             │
│  ITI: [5]–[10] sn                  │  Lick (toplam):  38             │
│  DS Süresi: [10] sn                │  ITI Press (trial): 0           │
│  Yanıt Penceresi: [10] sn          │  ITI Press (toplam): 1          │
│  Şok: [0.5]sn  [0.2]mA            │                                 │
│  Max Üst üste: [3]                 │  LOG                            │
│                                     │  > 10:32:01 Trial 3: DS+ ...   │
│  LEVER AYARLARI                    │  > 10:32:14 ÖDÜL, lick=5       │
│  Lever: [Sol ▼]                    │                                 │
│  [✓] DS'de lever çıksın            │                                 │
│                                     │                                 │
│  OUTCOME AYARLARI                  │                                 │
│  DS+ Outcome: [Ödül ▼]            │                                 │
│  DS− Outcome: [Ceza ▼]            │                                 │
│  Su tarafı:   [Sol ▼]              │                                 │
│                                     │                                 │
│  AVISOFT PLAYLIST                  │                                 │
│  DS+ .wav: [C:\sounds\ds_plus.wav] │                                 │
│  DS− .wav: [C:\sounds\ds_minus.wav]│                                 │
│  Playlist: [C:\sounds\playlist.txt]│                                 │
│                                     │                                 │
│  KONTROL                           │                                 │
│  [▶ Başlat]  [⏹ Durdur]          │                                 │
│                                     │                                 │
│  SİMÜLASYON KONTROLLERİ           │                                 │
│  [DS+] [DS−]                       │                                 │
│  [Lever Bas] [Lick]                │                                 │
│                                     │                                 │
│  DONANIM TESTİ                     │                                 │
│  [Lever Çıkar] [Lever Geri Al]     │                                 │
│  [Su Ver] [Şok (0.2sn)]            │                                 │
│  [Cue DS+ Yeşil] [Cue Söndür]     │                                 │
│  [BNC TTL Gönder (100ms)]          │                                 │
└─────────────────────────────────────┴─────────────────────────────────┘
```

---

## Çoklu Hayvan Oturumu

Bir sabah 4 hayvanı sırayla aynı kutuda çalıştırmak için:

1. Oturum başında hayvan listesine tüm ID'leri gir:
   ```
   RAT_01
   RAT_02
   RAT_03
   RAT_04
   ```
2. **Başlat** → RAT_01 başlar, üstte `Sıra: 1/4 — Şu an: RAT_01` görünür
3. RAT_01 bitince sonuç popup'ı açılır:
   - Hit Rate, CR Rate, d', log dosyası adı
   - **"Sonraki Hayvan: RAT_02 →"** butonu
   - **"Bitir"** butonu (listeyi yarıda kesmek için)
4. Butona basınca RAT_02 **aynı parametrelerle** otomatik başlar
5. Tüm liste bitince `"Tüm hayvanlar tamamlandı"` mesajı gösterilir

Her hayvanın verisi ayrı CSV dosyasına kaydedilir:
```
logs/session_RAT_01_20260322_090000.csv
logs/session_RAT_02_20260322_094500.csv
logs/session_RAT_03_20260322_103000.csv
logs/session_RAT_04_20260322_111500.csv
```

---

## Donanım Testi

Deneye başlamadan önce **Bağlan**'a bastıktan sonra her bileşeni ayrı ayrı test et:

| Buton | Ne test eder |
|---|---|
| **Lever Çıkar** | Lever fiziksel olarak çıkıyor mu? |
| **Lever Geri Al** | Lever geri giriyor mu? |
| **Su Ver** | Doğru taraftan su geliyor mu? Miktar yeterli mi? |
| **Şok (0.2 sn)** | Akım çalışıyor mu? *(dikkat)* |
| **Cue DS+ Yeşil** | Yeşil ışık yanıyor mu? |
| **Cue Söndür** | Işık sönüyor mu? |
| **BNC TTL Gönder** | Avisoft tetikleniyor mu, ses çalıyor mu? |

---

## Avisoft Ayarları

Her oturum başında yazılım otomatik olarak bir `playlist.txt` dosyası üretir. Bu dosya trial sırasına göre `ds_plus.wav` ve `ds_minus.wav` dosyalarını listeler.

### Adımlar

1. **GUI'de ses dosyası yollarını ayarla** (Avisoft Playlist bölümü):
   ```
   DS+ .wav  →  C:\sounds\ds_plus.wav
   DS− .wav  →  C:\sounds\ds_minus.wav
   Playlist  →  C:\sounds\playlist.txt
   ```

2. **Başlat'a basınca** `playlist.txt` otomatik üretilir

3. **Avisoft yazılımında:**
   - `File` → `Open` → `playlist.txt` dosyasını seç
   - **"Stop after each file"** seçeneğini işaretle ✓
   - Yazılımı hazır beklet

4. **Deney çalışınca:**
   - Her DS sunumunda operant kutu BNC çıkışından TTL pulse gönderilir
   - Avisoft bu pulse'u alır ve sıradaki ses dosyasını çalar
   - DS+ → 100ms TTL → `ds_plus.wav`
   - DS− → 200ms TTL → `ds_minus.wav`

### Senkronizasyon Güvenliği

Avisoft DOUT onay portu bağlıysa her trial'da ses onayı beklenir. Onay gelmezse:
- GUI log'unda kırmızıyla `CRITICAL: ⚠ SYNC MISS` uyarısı gösterilir
- CSV'de o satırda `sound_confirmed = 0` işaretlenir
- Deney durmadan devam eder

Analiz sırasında `sound_confirmed == 0` olan trialleri filtreleyip dışarıda bırakabilirsin.

---

## Parametreler ve Konfigürasyon

Tüm parametreler GUI'den ayarlanabilir, kod değiştirmeye gerek yoktur. Varsayılan değerler `config.py`'dadır.

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
| `WATER_SIDE` | `0x01` | `0x01` = Sol, `0x02` = Sağ (lever ile otomatik eşlenir) |
| `LEVER_EXTEND_ON_DS` | `True` | `True`: lever DS başlayınca çıkar |
| `BNC_DS_PLUS_DURATION` | `100` | DS+ TTL süresi (ms) |
| `BNC_DS_MINUS_DURATION` | `200` | DS− TTL süresi (ms) |

---

## Deney Protokolü

### Trial Sırası Üretimi

- Trial sırası **dengeli rastgele** üretilir (belirli DS+ oranı korunur)
- **Maksimum üst üste kısıtı:** Aynı DS tipi art arda en fazla N kez gelir (GUI'den ayarlanır, varsayılan 3)
- Playlist.txt trial sırasıyla otomatik eşlenir

### Tek Trial Akışı

```
ITI (5–10 sn, rastgele)
  ├── House light AÇIK (beyaz)
  ├── Lever İÇERİDE
  └── ITI lever press → iti_presses++ (dürtüsellik ölçümü)
       ↓
DS Sunumu
  ├── DS+: Cue light YEŞİL + BNC TTL 100ms → ds_plus.wav
  └── DS−: Cue light KIRMIZI + BNC TTL 200ms → ds_minus.wav
       ↓
Lever Uzar
  ├── LEVER_EXTEND_ON_DS=True  → DS başlayınca çıkar
  └── LEVER_EXTEND_ON_DS=False → Yanıt penceresinde çıkar
       ↓
Yanıt Penceresi (10 sn)
  ├── Lever basıldı + DS+ → Outcome (ödül/ceza)
  ├── Lever basıldı + DS− → Outcome (ödül/ceza)
  ├── Süre doldu + DS+   → OMISSION (hata)
  └── Süre doldu + DS−   → CORRECT REJECTION (doğru)
       ↓
Outcome
  ├── Ödül: Su dispenseri (N pulse) → Lick penceresi
  └── Ceza: Şok (ayarlanabilir mA ve süre)
       ↓
CSV'ye kaydet + diskriminasyon güncelle → Sonraki ITI
```

### Diskriminasyon Metrikleri

| Metrik | Formül |
|---|---|
| **Hit Rate** | DS+ triallarda basış sayısı / Toplam DS+ trial |
| **CR Rate** | DS− triallarda basılmayan / Toplam DS− trial |
| **d' (d-prime)** | Z(Hit Rate) − Z(False Alarm Rate) |

d' hesabı scipy kullanmadan rational approximation (probit) ile yapılır.

---

## Veri Çıktısı (CSV)

Her hayvan için ayrı dosya `logs/` klasörüne otomatik kaydedilir.

**Dosya adı formatı:** `session_<AnimalID>_<YYYYMMDD>_<HHMMSS>.csv`

### CSV Sütunları

| Sütun | Açıklama |
|---|---|
| `animal_id` | Hayvan ID |
| `trial` | Trial numarası (1'den başlar) |
| `ds_type` | `DS+` veya `DS-` |
| `result` | `rewarded`, `punished`, `omission`, `correct_rejection` |
| `rt_from_ds_s` | DS başlangıcından lever basışına süre (saniye) |
| `rt_from_lever_s` | Lever uzayışından basışa süre (saniye) |
| `lick_count` | Ödül sonrası toplam lick sayısı |
| `iti_presses` | Bu trialdaki ITI lever press sayısı |
| `hit_rate` | Kümülatif hit oranı |
| `cr_rate` | Kümülatif correct rejection oranı |
| `d_prime` | Kümülatif d' değeri |
| `rewarded` | Ödüllü trial sayısı (kümülatif) |
| `punished` | Cezalı trial sayısı (kümülatif) |
| `omission` | Omission sayısı (kümülatif) |
| `correct_rejection` | Correct rejection sayısı (kümülatif) |
| `sound_confirmed` | Avisoft ses onayı: `1` = onaylı, `0` = miss |
| `timestamp` | ISO 8601 zaman damgası |

---

## Simülasyon Modu

Donanım olmadan tüm yazılımı test etmek için:

1. GUI'de **"Simülasyon modu"** kutucuğunu işaretle (varsayılan: açık)
2. Port alanlarını boş bırak
3. **Bağlan** → **Başlat**
4. **Simülasyon Kontrolleri** butonlarını kullan:
   - **Lever Bas** — lever basışı simüle eder
   - **Lick** — lick eventi simüle eder

Tüm state machine, CSV loglama ve diskriminasyon metrikleri simülasyon modunda tam çalışır.

---

## Sistem Diyagramları

`diagrams/` klasöründe PlantUML kaynak dosyaları bulunur. [plantuml.com](https://plantuml.com) ile PNG'ye çevirebilirsiniz.

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
├── requirements.txt     # Python bağımlılıkları
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
