"""
Conduct Science Operant Box - Serial İletişim Katmanı
Protokol: 0xAA 0xBB [kanal] [tip] [data...] 0xCC 0xDD  |  Baud: 115200, 8N1
"""

import serial
import threading
import time
import logging
from typing import Callable, Optional


class OperantBox:
    BAUD_RATE = 115200
    START1, START2 = 0xAA, 0xBB
    END1,   END2   = 0xCC, 0xDD

    # PC → MCU komut tipleri
    CMD_TONE        = 0x01
    CMD_LIGHT_BOX   = 0x02
    CMD_IR_LIGHT    = 0x04
    CMD_SHOCK       = 0x05
    CMD_CUE_LIGHT   = 0x06
    CMD_PELLET      = 0x07
    CMD_FAN         = 0x08
    CMD_WATER       = 0x09
    CMD_HOUSE_LIGHT = 0x11
    CMD_LEVER       = 0x12
    CMD_PELLET_RGB  = 0x13
    CMD_BNC_TTL     = 0xB1

    # MCU → PC olay tipleri
    EVT_LEVER          = 0xF3
    EVT_FOOD_STATUS    = 0xF0
    EVT_FOOD_EATEN     = 0xA3
    EVT_FOOD_DISPENSED = 0xA4
    EVT_NOSE_POKE      = 0xA5

    # Lever alt tipleri
    LEVER_PRESS   = 0xA0
    LEVER_RELEASE = 0xC0
    LEVER_LEFT    = 0x01
    LEVER_RIGHT   = 0x02

    def __init__(self, port: str, channel: int = 0x01, simulated: bool = False):
        self.port      = port
        self.channel   = channel
        self.simulated = simulated
        self._serial   = None
        self._running  = False
        self._thread   = None
        self._buffer   = bytearray()
        self._callbacks: dict[str, list[Callable]] = {}
        self.log = logging.getLogger("OperantBox")

    # ── Bağlantı ──────────────────────────────────────────────────────────────

    def connect(self) -> bool:
        if self.simulated:
            self.log.info("Simülasyon modu aktif (gerçek kutu yok)")
            return True
        try:
            self._serial = serial.Serial(
                self.port, self.BAUD_RATE,
                bytesize=8, parity='N', stopbits=1, timeout=0.1,
                write_timeout=1.0
            )
            self._running = True
            self._thread = threading.Thread(target=self._read_loop, daemon=True)
            self._thread.start()
            self.log.info(f"Bağlandı: {self.port}")
            return True
        except serial.SerialException as e:
            self.log.error(f"Bağlantı hatası: {e}")
            return False

    def disconnect(self):
        self._running = False
        if self._serial and self._serial.is_open:
            self._serial.close()
        self.log.info("Bağlantı kesildi")

    def is_connected(self) -> bool:
        if self.simulated:
            return True
        return self._serial is not None and self._serial.is_open

    # ── Olay sistemi ──────────────────────────────────────────────────────────

    def on(self, event: str, callback: Callable):
        self._callbacks.setdefault(event, []).append(callback)

    def _emit(self, event: str, *args):
        for cb in self._callbacks.get(event, []):
            try:
                cb(*args)
            except Exception as e:
                self.log.error(f"Callback hatası [{event}]: {e}")

    # ── Seri okuma ────────────────────────────────────────────────────────────

    def _read_loop(self):
        while self._running:
            try:
                if self._serial and self._serial.in_waiting:
                    data = self._serial.read(self._serial.in_waiting)
                    self._buffer.extend(data)
                    self._parse_buffer()
                time.sleep(0.005)
            except serial.SerialException as e:
                self.log.error(f"Okuma hatası: {e}")
                self._emit('disconnected')
                break

    def _parse_buffer(self):
        while len(self._buffer) >= 8:
            # Başlangıç sırasını bul
            idx = -1
            for i in range(len(self._buffer) - 1):
                if self._buffer[i] == self.START1 and self._buffer[i+1] == self.START2:
                    idx = i
                    break
            if idx == -1:
                self._buffer.clear()
                return
            if idx > 0:
                self._buffer = self._buffer[idx:]

            if len(self._buffer) < 8:
                return

            # Bitiş sırasını bul
            end_idx = -1
            for i in range(2, min(len(self._buffer) - 1, 20)):
                if self._buffer[i] == self.END1 and self._buffer[i+1] == self.END2:
                    end_idx = i
                    break
            if end_idx == -1:
                if len(self._buffer) > 20:
                    self._buffer = self._buffer[2:]
                return

            packet = bytes(self._buffer[:end_idx + 2])
            self._buffer = self._buffer[end_idx + 2:]
            self._handle_packet(packet)

    def _handle_packet(self, packet: bytes):
        self.log.debug(f"RX: {packet.hex()}")
        if len(packet) < 6:
            return

        evt_type = packet[3]

        if evt_type == self.EVT_LEVER and len(packet) >= 8:
            subtype = packet[4]
            side    = packet[5]
            side_name = 'left' if side == self.LEVER_LEFT else 'right'
            if subtype == self.LEVER_PRESS:
                self.log.info(f"Lever basıldı: {side_name}")
                self._emit('lever_press', side_name)
            elif subtype == self.LEVER_RELEASE:
                self.log.info(f"Lever bırakıldı: {side_name}")
                self._emit('lever_release', side_name)

        elif evt_type == self.EVT_FOOD_STATUS:
            self.log.warning("Yem bitti!")
            self._emit('food_empty')

        elif evt_type == self.EVT_FOOD_EATEN and len(packet) >= 7:
            kind = packet[4]   # 0x01=yem, 0x02=su
            side = packet[5]
            if kind == 0x02:
                side_name = 'left' if side == self.LEVER_LEFT else 'right'
                self.log.debug(f"Lick: {side_name}")
                self._emit('lick', side_name)
            else:
                self.log.info("Yem yendi")
                self._emit('food_eaten')

        elif evt_type == self.EVT_FOOD_DISPENSED:
            self.log.info("Yem verildi")
            self._emit('food_dispensed')

    # ── Gönderme ──────────────────────────────────────────────────────────────

    def _send(self, data: bytes):
        self.log.debug(f"TX: {data.hex()}")
        if self.simulated:
            return
        if self._serial and self._serial.is_open:
            try:
                self._serial.write(data)
            except serial.SerialTimeoutException:
                self.log.error("Serial yazma timeout — donanım yanıt vermiyor")
            except serial.SerialException as e:
                self.log.error(f"Serial yazma hatası: {e}")
        else:
            self.log.warning("Seri port kapalı, paket gönderilemedi")

    def _packet(self, *data_bytes) -> bytes:
        return bytes([self.START1, self.START2, self.channel] + list(data_bytes) + [self.END1, self.END2])

    # ── Komutlar ──────────────────────────────────────────────────────────────

    def pellet(self):
        """Yem ver."""
        self._send(self._packet(self.CMD_PELLET, 0x01, 0x01, 0x00, 0x00))

    def water(self, side: int = 0x01):
        """Bir pulse su ver. side: 0x01=sol, 0x02=sağ."""
        self._send(self._packet(self.CMD_WATER, side, 0x01, 0x00, 0x00))

    def simulate_lick(self, side: str = 'left'):
        """Test için lick simüle et."""
        if self.simulated:
            self._emit('lick', side)

    def shock(self, on: bool):
        """Şok aç/kapat."""
        self._send(self._packet(self.CMD_SHOCK, 0x01 if on else 0x00, 0x00, 0x00, 0x00))

    def shock_current(self, ma: float):
        """Şok akım şiddetini ayarla. ma: 0.1 – 0.4 mA."""
        value = max(1, min(4, round(ma * 10)))
        self._send(self._packet(0x03, self.channel, value, 0x00, 0x00))

    def cue_light(self, side: int, r: int, g: int, b: int):
        """Cue ışığını ayarla. side: 0x01=sol, 0x02=sağ."""
        self._send(self._packet(self.CMD_CUE_LIGHT, side, r, g, b))

    def cue_light_off(self, side: int):
        """Cue ışığını söndür."""
        self.cue_light(side, 0, 0, 0)

    def house_light(self, r: int, g: int, b: int):
        """House light rengini ayarla."""
        self._send(self._packet(self.CMD_HOUSE_LIGHT, 0x01, r, g, b))

    def house_light_off(self):
        self.house_light(0, 0, 0)

    def lever_extend(self, side: int = LEVER_LEFT):
        """Lever'ı uzat."""
        self._send(self._packet(self.CMD_LEVER, side, 0x00, 0x00, 0x00))

    def lever_retract(self, side: int = LEVER_LEFT):
        """Lever'ı geri çek."""
        self._send(self._packet(self.CMD_LEVER, side, 0x01, 0x00, 0x00))

    def tone(self, volume: int, frequency: int):
        """Ses çal. volume: 0-100, frequency: Hz."""
        freq_high = (frequency >> 8) & 0xFF
        freq_low  = frequency & 0xFF
        self._send(self._packet(self.CMD_TONE, self.channel, 0x01, volume, freq_high, freq_low, 0x00))

    def bnc_ttl(self, voltage_v: float, duration_ms: int):
        """BNC TTL pulse gönder. voltage: 0.1-3.3V, duration: 1-1000ms."""
        vol_byte = max(1, min(33, int(voltage_v * 10)))
        dur_high = (duration_ms >> 8) & 0xFF
        dur_low  = duration_ms & 0xFF
        self._send(self._packet(self.CMD_BNC_TTL, vol_byte, dur_high, dur_low, 0x00))

    def simulate_lever_press(self, side: str = 'left'):
        """Test için lever press simüle et (sadece simülasyon modunda)."""
        if self.simulated:
            self._emit('lever_press', side)
