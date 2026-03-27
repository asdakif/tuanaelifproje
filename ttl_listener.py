"""
TTL Trigger — UltraSoundGate tetikleme
Seri portun RTS hattını pulse ederek UltraSoundGate'e TTL sinyali gönderir.
Port boş bırakılırsa simülasyon modunda çalışır (sadece loglama).
"""

import serial
import time
import logging


class TTLListener:
    """UltraSoundGate'e TTL trigger sinyali gönderir (RTS hattı üzerinden)."""

    def __init__(self, port: str = "", baud: int = 115200):
        self.port      = port
        self.baud      = baud
        self.simulated = (port == "")
        self._serial   = None
        self.log = logging.getLogger("TTLTrigger")

    def start(self) -> bool:
        if self.simulated:
            self.log.info("TTL simülasyon modu (port yok)")
            return True
        try:
            self._serial = serial.Serial(
                self.port, self.baud,
                timeout=0.1, write_timeout=1.0
            )
            self._serial.rts = False
            self.log.info(f"TTL portu açıldı: {self.port}")
            return True
        except serial.SerialException as e:
            self.log.error(f"TTL port hatası: {e}")
            return False

    def stop(self):
        if self._serial and self._serial.is_open:
            self._serial.rts = False
            self._serial.close()
        self.log.info("TTL portu kapatıldı")

    def send_trigger(self, duration_s: float = 0.01):
        """RTS hattını pulse et — UltraSoundGate'i tetikler."""
        if self.simulated:
            self.log.info(f"TTL trigger simüle edildi ({duration_s*1000:.0f}ms)")
            return
        if not self._serial or not self._serial.is_open:
            self.log.warning("TTL portu kapalı, trigger gönderilemedi")
            return
        try:
            self._serial.rts = True
            time.sleep(duration_s)
            self._serial.rts = False
            self.log.info(f"TTL trigger gönderildi ({duration_s*1000:.0f}ms)")
        except serial.SerialException as e:
            self.log.error(f"TTL trigger hatası: {e}")
