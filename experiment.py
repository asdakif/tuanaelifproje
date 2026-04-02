"""
Deney State Machine — DS+ / DS− Operant Koşullanma
"""

import threading
import time
import random
import math
import csv
import os
import logging
import subprocess
from enum import Enum, auto
from datetime import datetime
from typing import Callable, Optional

import config
from operant_box import OperantBox


class State(Enum):
    IDLE        = auto()
    ITI         = auto()
    DS_ON       = auto()
    RESPONSE    = auto()
    OUTCOME     = auto()
    SESSION_END = auto()


class DSType(Enum):
    PLUS  = "DS+"
    MINUS = "DS-"


class TrialResult(Enum):
    REWARDED          = "rewarded"           # lever basıldı + outcome=reward
    PUNISHED          = "punished"           # lever basıldı + outcome=punishment
    OMISSION          = "omission"           # DS+ + lever basılmadı (hata)
    CORRECT_REJECTION = "correct_rejection"  # DS− + lever basılmadı (doğru)


def _probit(p: float) -> float:
    """Normal dağılım ters CDF (probit) — d' hesabı için."""
    p = max(0.001, min(0.999, p))
    t = math.sqrt(-2.0 * math.log(min(p, 1 - p)))
    c = [2.515517, 0.802853, 0.010328]
    d = [1.432788, 0.189269, 0.001308]
    x = t - (c[0] + c[1]*t + c[2]*t*t) / (1 + d[0]*t + d[1]*t*t + d[2]*t*t*t)
    return -x if p < 0.5 else x


class Experiment:
    def __init__(self, box: OperantBox):
        self.box = box
        self.log = logging.getLogger("Experiment")

        # Oturum
        self.state      = State.IDLE
        self.session_id = ""
        self.animal_id  = ""

        # Trial durumu
        self.trial_num    = 0
        self.current_ds: Optional[DSType] = None
        self.lever_pressed   = False
        self.response_time_from_ds:    Optional[float] = None  # DS başından
        self.response_time_from_lever: Optional[float] = None  # Lever uzayınca
        self._ds_onset_time:    Optional[float] = None
        self._lever_extend_time: Optional[float] = None

        # ITI lever presses
        self.iti_presses      = 0   # Bu trial ITI'sında kaç kez basıldı
        self.total_iti_presses = 0  # Oturum geneli ITI basışları
        self._in_iti          = False

        # Lick
        self.lick_count      = 0
        self.total_licks     = 0
        self._counting_licks = False

        # Avisoft DOUT onayı
        self._sound_confirmed  = False
        self._sound_sync_misses = 0   # oturum geneli onaysız trial sayısı
        self._dout_event       = threading.Event()

        # İstatistikler
        self.stats = {
            "rewarded":          0,
            "punished":          0,
            "omission":          0,
            "correct_rejection": 0,
        }

        # Trial sırası
        self.trial_sequence:   list[DSType] = []
        self.trial_wav_files:  list[str]    = []

        # Thread kontrol
        self._stop_event    = threading.Event()
        self._lever_event   = threading.Event()
        self._main_thread: Optional[threading.Thread] = None

        # Callbacks
        self._on_state_change: list[Callable] = []
        self._on_trial_end:    list[Callable] = []
        self._on_lick_update:  list[Callable] = []
        self._on_disc_update:  list[Callable] = []
        self._on_iti_press:    list[Callable] = []

        # Log
        self._log_file:  Optional[str] = None
        self._csv_writer = None
        self._csv_file   = None

        # Bağlantılar
        self.box.on('lever_press', self._on_lever_press)
        self.box.on('lick',        self._on_lick)

        try:
            from avisoft_trigger import AvisoftTrigger
            self.avisoft_trigger = AvisoftTrigger()
        except ImportError:
            self.avisoft_trigger = None
            self.log.warning("avisoft_trigger yüklenemedi, yazılımsal trigger devre dışı")

    # ── Callback kayıt ────────────────────────────────────────────────────────

    def on_state_change(self, cb: Callable):
        self._on_state_change.append(cb)

    def on_trial_end(self, cb: Callable):
        self._on_trial_end.append(cb)

    def on_lick_update(self, cb: Callable):
        self._on_lick_update.append(cb)

    def on_discrimination_update(self, cb: Callable):
        """cb(hit_rate, cr_rate, d_prime) — her trial sonunda çağrılır."""
        self._on_disc_update.append(cb)

    def on_iti_press(self, cb: Callable):
        """cb(trial_iti_presses, total_iti_presses) — ITI'da lever basılınca."""
        self._on_iti_press.append(cb)

    def _emit_state(self):
        for cb in self._on_state_change:
            try:
                cb(self.state, self.trial_num, self.current_ds)
            except Exception as e:
                self.log.error(f"State callback: {e}")

    def _emit_trial(self, result: TrialResult, ds: DSType):
        for cb in self._on_trial_end:
            try:
                cb(self.trial_num, ds, result,
                   self.response_time_from_ds,
                   self.response_time_from_lever)
            except Exception as e:
                self.log.error(f"Trial callback: {e}")

    # ── Diskriminasyon metrikleri ──────────────────────────────────────────────

    def discrimination_metrics(self) -> tuple[float, float, float]:
        """
        Hit rate    = DS+ basış / toplam DS+ trial
        CR rate     = DS− basılmayış / toplam DS− trial
        d'          = Z(hit) − Z(false_alarm)
        """
        total_ds_plus  = sum(1 for ds in self.trial_sequence[:self.trial_num] if ds == DSType.PLUS)
        total_ds_minus = sum(1 for ds in self.trial_sequence[:self.trial_num] if ds == DSType.MINUS)

        hits  = self._hit_count
        fa    = self._fa_count

        hit_rate = hits  / total_ds_plus  if total_ds_plus  > 0 else 0.0
        fa_rate  = fa    / total_ds_minus if total_ds_minus > 0 else 0.0
        cr_rate  = 1.0 - fa_rate

        try:
            d_prime = _probit(hit_rate) - _probit(fa_rate)
        except Exception:
            d_prime = 0.0

        return hit_rate, cr_rate, d_prime

    def _emit_disc(self):
        hr, cr, dp = self.discrimination_metrics()
        for cb in self._on_disc_update:
            try:
                cb(hr, cr, dp)
            except Exception as e:
                self.log.error(f"Disc callback: {e}")

    # ── Sinyal işleyiciler ────────────────────────────────────────────────────

    def _on_lever_press(self, side: str):
        if self.state == State.ITI and self._in_iti:
            self.iti_presses      += 1
            self.total_iti_presses += 1
            self.log.warning(f"ITI lever press! Trial {self.trial_num} ITI: {self.iti_presses}")
            for cb in self._on_iti_press:
                try:
                    cb(self.iti_presses, self.total_iti_presses)
                except Exception as e:
                    self.log.error(f"ITI press callback: {e}")

        elif self.state == State.RESPONSE or (
                self.state == State.DS_ON and config.LEVER_EXTEND_ON_DS):
            now = time.time()
            if not self.lever_pressed:
                # İlk basış: tepki süresini kaydet
                self.lever_pressed = True
                self.response_time_from_ds    = now - self._ds_onset_time    if self._ds_onset_time    else None
                self.response_time_from_lever = now - self._lever_extend_time if self._lever_extend_time else None
            self._lever_event.set()
            # Her basışa anlık ödül/ceza
            threading.Thread(target=self._deliver_press_outcome, daemon=True).start()

    def _deliver_press_outcome(self):
        """Her lever basışına ödül/ceza ver."""
        ds = self.current_ds
        if ds is None:
            return
        try:
            outcome = config.DS_PLUS_OUTCOME if ds == DSType.PLUS else config.DS_MINUS_OUTCOME
            if outcome == "reward":
                self._counting_licks = True
                for _ in range(config.WATER_PULSES):
                    if self._stop_event.is_set():
                        break
                    self.box.water(config.WATER_SIDE)
                    self._stop_event.wait(config.WATER_PULSE_GAP_S)
                self._stop_event.wait(config.LICK_WINDOW_S)
                self._counting_licks = False
                self.log.info(
                    f"Trial {self.trial_num} — Basış ödülü: su, lick: {self.lick_count}")
            else:
                self.box.shock_current(config.SHOCK_CURRENT_MA)
                self.box.shock(True)
                self._stop_event.wait(config.SHOCK_DURATION_S)
                self.box.shock(False)
                self.log.info(
                    f"Trial {self.trial_num} — Basış cezası: {config.SHOCK_CURRENT_MA}mA şok")
        except Exception as e:
            self.log.error(f"Press outcome hatası: {e}")

    def _on_lick(self, side: str):
        if self._counting_licks:
            self.lick_count  += 1
            self.total_licks += 1
            self.log.debug(f"Lick — trial: {self.lick_count}, toplam: {self.total_licks}")
            for cb in self._on_lick_update:
                try:
                    cb(self.lick_count, self.total_licks)
                except Exception as e:
                    self.log.error(f"Lick callback: {e}")

    # ── Deney başlat / durdur ─────────────────────────────────────────────────

    def _launch_avisoft(self):
        # ── Zaten açık mı? ────────────────────────────────────────────────────
        if self.avisoft_trigger and self.avisoft_trigger._find_window():
            self.log.info("Avisoft zaten çalışıyor — yeni pencere açılmıyor.")
            self.avisoft_trigger.list_children()
            self.avisoft_trigger.start_recording()
            return

        # ── Playback ──────────────────────────────────────────────────────────
        pb_exe = config.AVISOFT_EXE
        pb_cfg = config.AVISOFT_PLAYBACK_CONFIG
        if pb_exe and os.path.isfile(pb_exe):
            try:
                args = [pb_exe, pb_cfg] if pb_cfg and os.path.isfile(pb_cfg) else [pb_exe]
                subprocess.Popen(args)
                self.log.info(f"Avisoft Playback başlatıldı: {pb_exe}")
                if pb_cfg and not os.path.isfile(pb_cfg):
                    self.log.warning(f"Playback config bulunamadı: {pb_cfg}")
            except Exception as e:
                self.log.error(f"Avisoft Playback başlatılamadı: {e}")
        else:
            self.log.info("Avisoft Playback exe bulunamadı, manuel başlatılmalı.")

        # ── Recorder (yalnızca ayrı bir exe belirtilmişse) ────────────────────
        rec_exe = config.AVISOFT_RECORD_EXE
        rec_cfg = config.AVISOFT_RECORD_CONFIG
        if rec_exe and rec_exe != pb_exe and os.path.isfile(rec_exe):
            try:
                args = [rec_exe, rec_cfg] if rec_cfg and os.path.isfile(rec_cfg) else [rec_exe]
                subprocess.Popen(args)
                self.log.info(f"Avisoft Recorder başlatıldı: {rec_exe}")
                if rec_cfg and not os.path.isfile(rec_cfg):
                    self.log.warning(f"Record config bulunamadı: {rec_cfg}")
            except Exception as e:
                self.log.error(f"Avisoft Recorder başlatılamadı: {e}")

        # ── Yüklenmesini bekle + pencere bul ──────────────────────────────────
        delay = config.AVISOFT_LAUNCH_DELAY_S
        self.log.info(f"Avisoft yüklensin diye {delay}s bekleniyor…")
        self._stop_event.wait(delay)
        if self.avisoft_trigger:
            self.avisoft_trigger._find_window()
            self.avisoft_trigger.list_children()
            # Recorder'da Ctrl+S ile kaydı başlat (trigger DS'de gönderilecek)
            self.avisoft_trigger.start_recording()

    def prepare_playlist(self, max_consecutive: int = 3) -> str:
        """Trial sırası oluştur ve Avisoft playlist dosyasını yaz (deney başlamadan)."""
        self.trial_sequence = self._make_trial_sequence(max_consecutive)
        return self.generate_avisoft_playlist()

    def start(self, max_consecutive: int = 3, animal_id: str = "",
              use_existing_playlist: bool = False):
        if self.state != State.IDLE:
            return
        self._stop_event.clear()
        self.animal_id         = animal_id or config.ANIMAL_ID
        self.trial_num         = 0
        self.total_licks       = 0
        self.total_iti_presses = 0
        self._hit_count         = 0
        self._fa_count          = 0
        self._sound_sync_misses = 0
        self.stats = {
            "rewarded": 0, "punished": 0,
            "omission": 0, "correct_rejection": 0,
        }
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        if not use_existing_playlist:
            self.trial_sequence = self._make_trial_sequence(max_consecutive)
            self.generate_avisoft_playlist()
        else:
            self._load_trial_sequence_from_playlist()
        self._launch_avisoft()
        self._open_log()
        self._main_thread = threading.Thread(target=self._run, daemon=True)
        self._main_thread.start()

    def stop(self):
        self._stop_event.set()
        self._lever_event.set()
        self._dout_event.set()
        self._in_iti = False
        self.log.info("Deney durduruldu")

    # ── Ana döngü ─────────────────────────────────────────────────────────────

    def _run(self):
        self.log.info(f"Deney başladı — Hayvan: {self.animal_id} — {config.NUM_TRIALS} trial")
        if self.avisoft_trigger:
            self.avisoft_trigger.start_recording()
            self.log.info("USV kaydi baslatildi")
        try:
            for trial_idx, ds_type in enumerate(self.trial_sequence):
                if self._stop_event.is_set():
                    break
                self.trial_num = trial_idx + 1
                self._run_trial(ds_type)

            if not self._stop_event.is_set():
                self.state = State.SESSION_END
                self._emit_state()
                hr, cr, dp = self.discrimination_metrics()
                self.log.info(
                    f"Deney tamamlandı — Hit: {hr:.1%} | CR: {cr:.1%} | d': {dp:.2f}"
                )
        finally:
            if self.avisoft_trigger:
                self.avisoft_trigger.stop_recording()
                self.log.info("USV kaydi durduruldu")
            self._in_iti = False
            self.box.shock(False)
            self.box.house_light_off()
            self.box.lever_retract(config.LEVER_SIDE)
            time.sleep(0.05)
            self.box.lever_retract(config.LEVER_SIDE)
            if self._csv_file:
                self._csv_file.close()
                self._csv_file = None
            if self.state != State.IDLE:
                self.state = State.IDLE
                self._emit_state()

    def _run_trial(self, ds_type: DSType):
        # ── 1. ITI ───────────────────────────────────────────────────────────
        self.state               = State.ITI
        self.current_ds          = None
        self.lever_pressed       = False
        self.response_time_from_ds    = None
        self.response_time_from_lever = None
        self.lick_count          = 0
        self.iti_presses         = 0
        self._counting_licks     = False
        self._lever_extend_time  = None
        self._lever_event.clear()
        self._emit_state()

        self.box.lever_retract(config.LEVER_SIDE)
        time.sleep(0.05)
        self.box.lever_retract(config.LEVER_SIDE)
        r, g, b = config.HOUSE_LIGHT_COLOR
        self.box.house_light(r, g, b)

        iti = random.uniform(config.ITI_MIN_S, config.ITI_MAX_S)
        self.log.info(f"Trial {self.trial_num} [{ds_type.value}] — ITI: {iti:.1f}s")
        self._in_iti = True
        if self._stop_event.wait(iti):
            self._in_iti = False
            return
        self._in_iti = False

        if self.iti_presses > 0:
            self.log.warning(f"Trial {self.trial_num} — ITI'da {self.iti_presses} lever press!")

        # ── 2. DS Sunumu ──────────────────────────────────────────────────────
        self.state          = State.DS_ON
        self.current_ds     = ds_type
        self._ds_onset_time = time.time()
        self._emit_state()

        # Avisoft trigger önce gönderilir — config kaydetme gecikmesini absorbe eder
        if self.avisoft_trigger:
            self.avisoft_trigger.trigger()

        if ds_type == DSType.PLUS:
            self.box.bnc_ttl(config.BNC_DS_PLUS_VOLTAGE, config.BNC_DS_PLUS_DURATION)
        else:
            self.box.bnc_ttl(config.BNC_DS_MINUS_VOLTAGE, config.BNC_DS_MINUS_DURATION)

        self.box.house_light_off()

        # Avisoft DOUT onayı (opsiyonel)
        self._sound_confirmed = True  # DOUT yoksa onaylı say
        if config.AVISOFT_DOUT_PORT:
            self._dout_event.clear()
            self._sound_confirmed = self._dout_event.wait(timeout=2.0)
            if self._sound_confirmed:
                self.log.info(f"Trial {self.trial_num} — Avisoft ses onaylandı ✓")
            else:
                self._sound_sync_misses += 1
                self.log.critical(
                    f"⚠ SYNC MISS — Trial {self.trial_num} [{ds_type.value}]: "
                    f"Avisoft DOUT onayı gelmedi! "
                    f"(Toplam {self._sound_sync_misses} miss bu oturumda) "
                    f"Playlist sırası kaymış olabilir — verileri kontrol et."
                )

        if config.LEVER_EXTEND_ON_DS:
            # Yanıt gecikmesi — lever bu süre kadar geri kalır
            if config.RESPONSE_DELAY_S > 0:
                if self._stop_event.wait(config.RESPONSE_DELAY_S):
                    return
            time.sleep(0.05)
            self._lever_extend_time = time.time()
            self.box.lever_extend(config.LEVER_SIDE)
            time.sleep(0.05)
            self.box.lever_extend(config.LEVER_SIDE)
            self.log.info(f"Trial {self.trial_num} — {ds_type.value} + lever uzatıldı")
            # DS onset'ten itibaren DS_DURATION_S dolana kadar bekle (lever basılınca çık)
            ds_end = self._ds_onset_time + config.DS_DURATION_S
            while not self._stop_event.is_set() and time.time() < ds_end:
                remaining = ds_end - time.time()
                if self._lever_event.wait(min(0.05, remaining)):
                    break
            if self._stop_event.is_set():
                return
        else:
            self.log.info(f"Trial {self.trial_num} — {ds_type.value} sunuldu")
            if self._stop_event.wait(config.DS_DURATION_S):
                return

        # ── 3. Yanıt Penceresi ────────────────────────────────────────────────
        self.state = State.RESPONSE
        if not self.lever_pressed:
            self._lever_event.clear()
        self._emit_state()

        if not config.LEVER_EXTEND_ON_DS:
            # Yanıt gecikmesi
            if config.RESPONSE_DELAY_S > 0:
                if self._stop_event.wait(config.RESPONSE_DELAY_S):
                    return
            time.sleep(0.05)
            self._lever_extend_time = time.time()
            self.box.lever_extend(config.LEVER_SIDE)
            time.sleep(0.05)
            self.box.lever_extend(config.LEVER_SIDE)
            self.log.info(f"Trial {self.trial_num} — Lever uzatıldı")

        # Yanıt penceresini tam süre bekle — lever basılmış olsa bile dışarıda kalır
        resp_end = time.time() + config.RESPONSE_WINDOW_S
        while not self._stop_event.is_set() and time.time() < resp_end:
            remaining = resp_end - time.time()
            self._lever_event.wait(min(0.05, remaining))
        pressed = self.lever_pressed

        # ── 4. Outcome ────────────────────────────────────────────────────────
        self.state = State.OUTCOME
        self._emit_state()

        self.box.lever_retract(config.LEVER_SIDE)
        time.sleep(0.05)
        self.box.lever_retract(config.LEVER_SIDE)

        rt_ds    = f"{self.response_time_from_ds:.3f}s"    if self.response_time_from_ds    else "—"
        rt_lever = f"{self.response_time_from_lever:.3f}s" if self.response_time_from_lever else "—"

        if pressed and self.lever_pressed:
            outcome = config.DS_PLUS_OUTCOME if ds_type == DSType.PLUS else config.DS_MINUS_OUTCOME
            if outcome == "reward":
                result = TrialResult.REWARDED
                self.stats["rewarded"] += 1
                self._hit_count += (1 if ds_type == DSType.PLUS else 0)
                self._fa_count  += (1 if ds_type == DSType.MINUS else 0)
                self.log.info(
                    f"Trial {self.trial_num} → ÖDÜL [{ds_type.value}] "
                    f"RT(DS)={rt_ds} RT(lever)={rt_lever}"
                )
            else:
                result = TrialResult.PUNISHED
                self.stats["punished"] += 1
                self._hit_count += (1 if ds_type == DSType.PLUS else 0)
                self._fa_count  += (1 if ds_type == DSType.MINUS else 0)
                self.log.info(
                    f"Trial {self.trial_num} → CEZA [{ds_type.value}] "
                    f"RT(DS)={rt_ds} RT(lever)={rt_lever} "
                    f"{config.SHOCK_CURRENT_MA}mA"
                )
        else:
            if ds_type == DSType.PLUS:
                result = TrialResult.OMISSION
                self.stats["omission"] += 1
                self.log.info(f"Trial {self.trial_num} → OMISSION (DS+ basılmadı)")
            else:
                result = TrialResult.CORRECT_REJECTION
                self.stats["correct_rejection"] += 1
                self.log.info(f"Trial {self.trial_num} → CORRECT REJECTION (DS− basılmadı ✓)")

        self._emit_trial(result, ds_type)
        self._emit_disc()
        self._log_trial(result, ds_type)

    # ── Trial sırası ──────────────────────────────────────────────────────────

    def _load_trial_sequence_from_playlist(self):
        """Mevcut playlist dosyasindan trial sirasini oku"""
        playlist_path = config.AVISOFT_PLAYLIST
        if not os.path.exists(playlist_path):
            self.log.error(f"Playlist bulunamadi: {playlist_path}")
            return
        with open(playlist_path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]

        self.trial_sequence = []
        self.trial_wav_files = lines[:]
        for line in lines:
            basename = os.path.basename(line).lower()
            is_plus = False
            if config.DS_PLUS_WAV and os.path.basename(config.DS_PLUS_WAV).lower() == basename:
                is_plus = True
            elif config.DS_PLUS_WAV_LIST:
                for wav in config.DS_PLUS_WAV_LIST:
                    if os.path.basename(wav).lower() == basename:
                        is_plus = True
                        break
            self.trial_sequence.append(DSType.PLUS if is_plus else DSType.MINUS)

        config.NUM_TRIALS = len(self.trial_sequence)
        self.log.info(f"Mevcut playlist'ten yuklendi: {len(self.trial_sequence)} trial")

    def _make_trial_sequence(self, max_consecutive: int = 3) -> list[DSType]:
        n_plus  = round(config.NUM_TRIALS * config.DS_PLUS_RATIO)
        n_minus = config.NUM_TRIALS - n_plus
        seq     = [DSType.PLUS] * n_plus + [DSType.MINUS] * n_minus

        for _ in range(10_000):
            random.shuffle(seq)
            ok = True
            count = 1
            for i in range(1, len(seq)):
                if seq[i] == seq[i - 1]:
                    count += 1
                    if count > max_consecutive:
                        ok = False
                        break
                else:
                    count = 1
            if ok:
                self.log.info(f"Trial sırası: {len(seq)} trial, max {max_consecutive} üst üste")
                return seq

        self.log.warning("Üst üste kısıt sağlanamadı")
        return seq

    # ── Avisoft Playlist ──────────────────────────────────────────────────────

    def generate_avisoft_playlist(self) -> str:
        import random as _rnd
        lines = []
        self.trial_wav_files = []
        for ds in self.trial_sequence:
            if ds == DSType.PLUS:
                wav = _rnd.choice(config.DS_PLUS_WAV_LIST) if config.DS_PLUS_WAV_LIST else config.DS_PLUS_WAV
            else:
                wav = _rnd.choice(config.DS_MINUS_WAV_LIST) if config.DS_MINUS_WAV_LIST else config.DS_MINUS_WAV
            lines.append(wav)
            self.trial_wav_files.append(wav)

        playlist_path = config.AVISOFT_PLAYLIST
        parent = os.path.dirname(playlist_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(playlist_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        from collections import Counter
        counts = Counter(lines)
        count_str = ", ".join(f"{os.path.basename(k)}:{v}" for k, v in counts.items())
        self.log.info(f"Playlist: {playlist_path} ({len(lines)} ses, {count_str})")
        return playlist_path

    # ── CSV Log ───────────────────────────────────────────────────────────────

    def _open_log(self):
        os.makedirs(config.LOG_DIR, exist_ok=True)
        self._log_file = os.path.join(
            config.LOG_DIR,
            f"session_{self.animal_id}_{self.session_id}.csv"
        )
        self._csv_file   = open(self._log_file, "w", newline="", encoding="utf-8")
        self._csv_writer = csv.writer(self._csv_file)
        self._csv_writer.writerow([
            "animal_id", "trial", "ds_type", "result",
            "rt_from_ds_s", "rt_from_lever_s", "lick_count", "iti_presses",
            "timestamp",
            "hit_rate", "cr_rate", "d_prime",
            "rewarded", "punished", "omission", "correct_rejection",
            "sound_confirmed", "criterion_reached", "wav_file",
        ])
        self.log.info(f"Log: {self._log_file}")

    def _log_trial(self, result: TrialResult, ds: DSType):
        if not self._csv_writer:
            return
        hr, cr, dp = self.discrimination_metrics()
        wav = (self.trial_wav_files[self.trial_num - 1]
               if self.trial_wav_files and self.trial_num - 1 < len(self.trial_wav_files)
               else "")
        self._csv_writer.writerow([
            self.animal_id,
            self.trial_num,
            ds.value,
            result.value,
            f"{self.response_time_from_ds:.4f}"    if self.response_time_from_ds    else "",
            f"{self.response_time_from_lever:.4f}" if self.response_time_from_lever else "",
            self.lick_count,
            self.iti_presses,
            datetime.now().isoformat(),
            f"{hr:.3f}", f"{cr:.3f}", f"{dp:.3f}",
            self.stats["rewarded"],
            self.stats["punished"],
            self.stats["omission"],
            self.stats["correct_rejection"],
            int(self._sound_confirmed),
            int(hr >= config.CRITERION_HIT_RATE and dp >= config.CRITERION_DPRIME),
            wav,
        ])
        self._csv_file.flush()
