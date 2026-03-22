# Operant Koşullanma Deney Yazılımı

**DS+/DS− Discriminative Stimulus Paradigm Controller**
Boğaziçi Üniversitesi — Davranışsal Nörobilim Laboratuvarı

---

Bu yazılım, Conduct Science operant kutusu ile **DS+/DS− diskriminatif stimulus** paradigması üzerinden **operant koşullanma** deneyleri yürütmek için geliştirilmiştir. Tüm parametreler GUI üzerinden ayarlanır, kod değiştirmeye gerek yoktur.

## Hızlı Başlangıç

```bash
git clone https://github.com/asdakif/tuanaelifproje.git
cd tuanaelifproje
pip install -r requirements.txt
python main.py
```

1. Hayvan listesini gir (her satıra bir ID)
2. **Bağlan** → **Donanım Testi** → **Başlat**
3. Avisoft'ta `playlist.txt` dosyasını aç, **"Stop after each file"** işaretle
4. Deney otomatik ilerler, her hayvan için ayrı CSV kaydedilir

## Özellikler

- DS+/DS− paradigması — ödül ve ceza outcome'ları konfigüre edilebilir
- Çoklu hayvan desteği — liste gir, hayvanlar sırayla otomatik çalışır
- Avisoft Player 116H entegrasyonu — BNC TTL trigger + playlist
- Canlı diskriminasyon metrikleri — Hit Rate, CR Rate, d'
- Donanım testi paneli — deney öncesi her bileşeni doğrula
- Lickometre, dual RT, ITI lever press (dürtüsellik) desteği
- Simülasyon modu — donanım olmadan tam test

## Dokümantasyon

Detaylı bilgi için **[Wiki](https://github.com/asdakif/tuanaelifproje/wiki)** sayfalarına bak:

| Sayfa | İçerik |
|---|---|
| [Kurulum](https://github.com/asdakif/tuanaelifproje/wiki/Kurulum) | Gereksinimler, donanım bağlantısı |
| [Arayüz Rehberi](https://github.com/asdakif/tuanaelifproje/wiki/Arayüz-Rehberi) | GUI panellerinin detaylı açıklaması |
| [Deney Protokolü](https://github.com/asdakif/tuanaelifproje/wiki/Deney-Protokolü) | Trial akışı, state machine, metrikler |
| [Çoklu Hayvan Oturumu](https://github.com/asdakif/tuanaelifproje/wiki/Çoklu-Hayvan-Oturumu) | Sıralı hayvan çalıştırma |
| [Donanım Testi](https://github.com/asdakif/tuanaelifproje/wiki/Donanım-Testi) | Deney öncesi bileşen doğrulama |
| [Avisoft Ayarları](https://github.com/asdakif/tuanaelifproje/wiki/Avisoft-Ayarları) | Playlist ve TTL trigger kurulumu |
| [Veri Çıktısı](https://github.com/asdakif/tuanaelifproje/wiki/Veri-Çıktısı) | CSV formatı ve sütun açıklamaları |
| [Simülasyon Modu](https://github.com/asdakif/tuanaelifproje/wiki/Simülasyon-Modu) | Donanımsız test rehberi |
