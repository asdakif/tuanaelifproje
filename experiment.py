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
from ttl_listener import TTLListener


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
    def __init__(self, box: OperantBox, ttl: TTLListener):
        self.box = box
        self.ttl = ttl
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
        self.trial_sequence: list[DSType] = []

        # Thread kontrol
        self._stop_event  = threading.Event()
        self._lever_event = threading.Event()
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
            self.lever_pressed = True
            now = time.time()
            self.response_time_from_ds    = now - self._ds_onset_time    if self._ds_onset_time    else None
            self.response_time_from_lever = now - self._lever_extend_time if self._lever_extend_time else None
            self._lever_event.set()

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
        exe = config.AVISOFT_EXE
        playlist = config.AVISOFT_PLAYLIST
        if not exe or not os.path.isfile(exe):
            self.log.info("Avisoft exe bulunamadı, manuel başlatılmalı.")
            return
        try:
            subprocess.Popen([exe, playlist])
            self.log.info(f"Avisoft başlatıldı: {exe}")
            delay = config.AVISOFT_LAUNCH_DELAY_S
            self.log.info(f"Avisoft yüklensin diye {delay}s bekleniyor…")
            self._stop_event.wait(delay)
        except Exception as e:
            self.log.error(f"Avisoft başlatılamadı: {e}")

    def prepare_playlist(self, max_consecutive: int = 3) -> str:
        """Trial sırası oluştur ve Avisoft playlist dosyasını yaz (deney başlamadan)."""
        self.trial_sequence = self._make_trial_sequence(max_consecutive)
        return self.generate_avisoft_playlist()

    def start(self, max_consecutive: int = 3, animal_id: str = ""):
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
        if not self.trial_sequence:
            self.trial_sequence = self._make_trial_sequence(max_consecutive)
            self.generate_avisoft_playlist()
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
            self._in_iti = False
            self.box.shock(False)
            self.box.cue_light_off(config.LEVER_SIDE)
            self.box.house_light_off()
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
        self._emit_state()

        self.box.lever_retract(config.LEVER_SIDE)
        r, g, b = config.HOUSE_LIGHT_COLOR
        self.box.house_light(r, g, b)
        self.box.cue_light_off(config.LEVER_SIDE)

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

        self.ttl.send_trigger(config.TTL_TRIGGER_DURATION_S)

        if ds_type == DSType.PLUS:
            r, g, b = config.CUE_DS_PLUS_COLOR
            self.box.bnc_ttl(config.BNC_DS_PLUS_VOLTAGE, config.BNC_DS_PLUS_DURATION)
        else:
            r, g, b = config.CUE_DS_MINUS_COLOR
            self.box.bnc_ttl(config.BNC_DS_MINUS_VOLTAGE, config.BNC_DS_MINUS_DURATION)

        self.box.cue_light(config.LEVER_SIDE, r, g, b)
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
            self._lever_extend_time = time.time()
            self.box.lever_extend(config.LEVER_SIDE)
            self.log.info(f"Trial {self.trial_num} — {ds_type.value} + lever uzatıldı")
        else:
            self.log.info(f"Trial {self.trial_num} — {ds_type.value} sunuldu")

        if self._stop_event.wait(config.DS_DURATION_S):
            return

        # ── 3. Yanıt Penceresi ────────────────────────────────────────────────
        self.state = State.RESPONSE
        # If lever was already pressed during DS_ON, keep the event/flag intact
        if not self.lever_pressed:
            self._lever_event.clear()
        self._emit_state()

        if not config.LEVER_EXTEND_ON_DS:
            self._lever_extend_time = time.time()
            self.box.lever_extend(config.LEVER_SIDE)
            self.log.info(f"Trial {self.trial_num} — Lever uzatıldı")

        pressed = self._lever_event.wait(config.RESPONSE_WINDOW_S)

        # ── 4. Outcome ────────────────────────────────────────────────────────
        self.state = State.OUTCOME
        self._emit_state()

        self.box.lever_retract(config.LEVER_SIDE)
        self.box.cue_light_off(config.LEVER_SIDE)

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
                self._counting_licks = True
                for _ in range(config.WATER_PULSES):
                    if self._stop_event.is_set():
                        break
                    self.box.water(config.WATER_SIDE)
                    self._stop_event.wait(config.WATER_PULSE_GAP_S)
                self._stop_event.wait(config.LICK_WINDOW_S)
                self._counting_licks = False
                r, g, b = config.HOUSE_LIGHT_COLOR
                self.box.house_light(r, g, b)
                self.log.info(f"Trial {self.trial_num} — Lick: {self.lick_count}")
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
                self.box.shock_current(config.SHOCK_CURRENT_MA)
                self.box.shock(True)
                self._stop_event.wait(config.SHOCK_DURATION_S)
                self.box.shock(False)
                r, g, b = config.HOUSE_LIGHT_COLOR
                self.box.house_light(r, g, b)
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
        lines = [
            config.DS_PLUS_WAV if ds == DSType.PLUS else config.DS_MINUS_WAV
            for ds in self.trial_sequence
        ]
        playlist_path = config.AVISOFT_PLAYLIST
        parent = os.path.dirname(playlist_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(playlist_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        self.log.info(f"Playlist: {playlist_path} ({len(lines)} ses, "
                      f"DS+:{lines.count(config.DS_PLUS_WAV)} "
                      f"DS−:{lines.count(config.DS_MINUS_WAV)})")
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
            "sound_confirmed", "criterion_reached",
        ])
        self.log.info(f"Log: {self._log_file}")

    def _log_trial(self, result: TrialResult, ds: DSType):
        if not self._csv_writer:
            return
        hr, cr, dp = self.discrimination_metrics()
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
        ])
        self._csv_file.flush()
