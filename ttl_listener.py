"""
TTL Sinyal Dinleyici — UltraSoundGate / Avisoft entegrasyonu
Mod 1: Seri port (TTL hardware $990 ile)
Mod 2: Simülasyon (hardware olmadan test)
"""

import serial
import threading
import logging
from typing import Callable


class TTLListener:
    """
    UltraSoundGate'ten DS+ ve DS− sinyallerini dinler.

    Hardware modu:
        TTL donanım kutusundan gelen seri mesajlar:
        - DS+ geldiğinde: 0x01 byte
        - DS− geldiğinde: 0x02 byte

    Simülasyon modu:
        GUI'den manuel tetikleme.
    """

    DS_PLUS  = "DS+"
    DS_MINUS = "DS-"

    def __init__(self, port: str = "", baud: int = 115200):
        self.port      = port
        self.baud      = baud
        self.simulated = (port == "")
        self._running  = False
        self._serial   = None
        self._thread   = None
        self._on_ds: list[Callable[[str], None]] = []
        self.log = logging.getLogger("TTLListener")

    def on_ds_signal(self, callback: Callable[[str], None]):
        """DS+ veya DS− sinyali geldiğinde çağrılacak fonksiyon."""
        self._on_ds.append(callback)

    def _emit(self, ds_type: str):
        self.log.info(f"DS sinyali: {ds_type}")
        for cb in self._on_ds:
            try:
                cb(ds_type)
            except Exception as e:
                self.log.error(f"DS callback hatası: {e}")

    def start(self) -> bool:
        if self.simulated:
            self.log.info("TTL simülasyon modu (port yok)")
            return True
        try:
            self._serial = serial.Serial(self.port, self.baud, timeout=0.1)
            self._running = True
            self._thread = threading.Thread(target=self._listen_loop, daemon=True)
            self._thread.start()
            self.log.info(f"TTL dinleniyor: {self.port}")
            return True
        except serial.SerialException as e:
            self.log.error(f"TTL port hatası: {e}")
            return False

    def stop(self):
        self._running = False
        if self._serial and self._serial.is_open:
            self._serial.close()

    def _listen_loop(self):
        """
        Hardware TTL kutusundan byte okur.
        0x01 → DS+, 0x02 → DS−
        """
        while self._running:
            try:
                if self._serial and self._serial.in_waiting:
                    byte = self._serial.read(1)[0]
                    if byte == 0x01:
                        self._emit(self.DS_PLUS)
                    elif byte == 0x02:
                        self._emit(self.DS_MINUS)
            except serial.SerialException as e:
                self.log.error(f"TTL okuma hatası: {e}")
                break

    # ── Simülasyon ────────────────────────────────────────────────────────────

    def simulate_ds_plus(self):
        """Test: DS+ sinyali simüle et."""
        if self.simulated:
            self._emit(self.DS_PLUS)

    def simulate_ds_minus(self):
        """Test: DS− sinyali simüle et."""
        if self.simulated:
            self._emit(self.DS_MINUS)
