import ctypes
import ctypes.wintypes
import logging
import time

try:
    import win32gui
    import win32con
    import win32api
    import win32process
except ImportError:
    win32gui = None


# ── SendInput yapıları (kayıt başlatmak için) ──────────────────────────────

class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk",         ctypes.wintypes.WORD),
        ("wScan",       ctypes.wintypes.WORD),
        ("dwFlags",     ctypes.wintypes.DWORD),
        ("time",        ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]

class _INPUT_UNION(ctypes.Union):
    _fields_ = [("ki", _KEYBDINPUT)]

class _INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.wintypes.DWORD), ("_input", _INPUT_UNION)]

_KEYEVENTF_KEYUP = 0x0002


def _send_key(vk: int, key_up: bool = False):
    scan  = ctypes.windll.user32.MapVirtualKeyW(vk, 0)
    flags = _KEYEVENTF_KEYUP if key_up else 0
    inp = _INPUT(
        type=1,
        _input=_INPUT_UNION(ki=_KEYBDINPUT(
            wVk=vk, wScan=scan, dwFlags=flags, time=0,
            dwExtraInfo=ctypes.cast(ctypes.pointer(ctypes.c_ulong(0)),
                                    ctypes.POINTER(ctypes.c_ulong))
        ))
    )
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))


class AvisoftTrigger:
    def __init__(self):
        self.log            = logging.getLogger("AvisoftTrigger")
        self._hwnd          = None   # Ana RECORDER USGH penceresi
        self._hwnd_playlist = None   # Playlist penceresi
        self._recorder_hwnd = None
        if win32gui is None:
            self.log.warning("pywin32 yüklü değil — pip install pywin32")
        else:
            self._find_window()  # Başlangıçta pencereyi bul ve logla

    # ── Pencere bulma ──────────────────────────────────────────────────────

    def list_windows(self):
        """Tüm görünür pencereleri logla — doğru başlığı bulmak için."""
        if win32gui is None:
            return
        titles = []
        def cb(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                t = win32gui.GetWindowText(hwnd)
                if t:
                    titles.append(f"  [{t}]  hwnd={hwnd}")
            return True
        win32gui.EnumWindows(cb, None)
        self.log.info("Açık pencereler:\n" + "\n".join(titles))

    def _find_window(self) -> bool:
        """
        İki pencere arar:
        - self._hwnd_playlist : "RECORDER Playlist" penceresi (Shift+Space hedefi)
        - self._hwnd           : Ana "RECORDER USGH" penceresi (yedek)
        Trigger önce playlist penceresini, yoksa ana pencereyi kullanır.
        """
        if win32gui is None:
            return False
        playlist_wins = []
        recorder_wins = []
        def cb(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return True
            title = win32gui.GetWindowText(hwnd)
            upper = title.upper()
            if "PLAYLIST" in upper and ("RECORDER" in upper or "AVISOFT" in upper):
                playlist_wins.append((hwnd, title))
            elif "USGH" in upper or ("RECORDER" in upper and "PLAYLIST" not in upper):
                recorder_wins.append((hwnd, title))
            return True
        win32gui.EnumWindows(cb, None)

        if not playlist_wins and not recorder_wins:
            self.log.error("Avisoft penceresi bulunamadı.")
            self.list_windows()
            return False

        self._hwnd_playlist = playlist_wins[0][0] if playlist_wins else None
        self._hwnd          = (recorder_wins[0][0] if recorder_wins
                               else playlist_wins[0][0])

        self.log.info(
            f"Avisoft ana pencere : [{recorder_wins[0][1] if recorder_wins else '—'}]  "
            f"hwnd={self._hwnd}\n"
            f"  Playlist penceresi: [{playlist_wins[0][1] if playlist_wins else '—'}]  "
            f"hwnd={self._hwnd_playlist}"
        )
        return True

    def list_children(self):
        """Avisoft pencerelerinin tüm child'larını logla — doğru hedefi bulmak için."""
        if not self._hwnd:
            self._find_window()
        if not self._hwnd:
            return
        for parent_hwnd, label in [
            (self._hwnd_playlist, "Playlist"),
            (self._hwnd, "Ana"),
        ]:
            if not parent_hwnd:
                continue
            children = []
            def cb(hwnd, _):
                cls   = win32gui.GetClassName(hwnd)
                title = win32gui.GetWindowText(hwnd)
                vis   = win32gui.IsWindowVisible(hwnd)
                children.append(f"  hwnd={hwnd}  cls=[{cls}]  title=[{title}]  visible={vis}")
                return True
            win32gui.EnumChildWindows(parent_hwnd, cb, None)
            self.log.info(
                f"Avisoft {label} [{parent_hwnd}] child windows ({len(children)}):\n"
                + "\n".join(children)
            )

    def _find_start_button(self) -> int:
        """
        Playlist penceresindeki Start/Play butonunu bul.
        Buton metninde 'start', 'play', 'başlat' geçen ilk Button child'ı döndürür.
        """
        if not self._hwnd_playlist:
            return 0
        found = [0]
        KEYWORDS = {"start", "play", "başlat", "go", "çal"}
        def cb(hwnd, _):
            if found[0]:
                return True
            cls = win32gui.GetClassName(hwnd).lower()
            if "button" in cls:
                title = win32gui.GetWindowText(hwnd).lower().strip()
                if any(k in title for k in KEYWORDS) or title == "":
                    # Boş başlıklı ilk button da aday (ikon buton olabilir)
                    if not found[0]:
                        found[0] = hwnd
            return True
        win32gui.EnumChildWindows(self._hwnd_playlist, cb, None)
        if found[0]:
            self.log.debug(
                f"Start butonu bulundu: hwnd={found[0]} "
                f"title=[{win32gui.GetWindowText(found[0])}]"
            )
        return found[0]

    # ── Kayıt penceresi ────────────────────────────────────────────────────

    def _find_recorder(self):
        import config
        if win32gui is None:
            return False

        target = config.AVISOFT_RECORDER_WINDOW.strip()

        def callback(hwnd, results):
            if not win32gui.IsWindowVisible(hwnd):
                return True
            title = win32gui.GetWindowText(hwnd)
            if not title:
                return True
            results.append((hwnd, title))
            return True

        results = []
        win32gui.EnumWindows(callback, results)

        # Once tam eslesme ara
        for hwnd, title in results:
            if title.strip() == target:
                self._recorder_hwnd = hwnd
                self.log.info(f"Recorder penceresi bulundu: '{title}'")
                return True

        # Tam eslesme yoksa #2 iceren RECORDER penceresi ara
        for hwnd, title in results:
            if "#2" in title and "RECORDER" in title.upper():
                self._recorder_hwnd = hwnd
                self.log.info(f"Recorder penceresi bulundu: '{title}'")
                return True

        self.log.error(f"Recorder penceresi bulunamadi! '{target}' baslikli pencere acik mi?")
        return False

    # ── Kayıt başlatma ─────────────────────────────────────────────────────

    def start_recording(self):
        """Kayit RECORDER penceresine Ctrl+S gonder"""
        if win32gui is None:
            return False
        if not self._recorder_hwnd or not win32gui.IsWindow(self._recorder_hwnd):
            if not self._find_recorder():
                return False
        try:
            current_hwnd = win32gui.GetForegroundWindow()
            win32gui.SetForegroundWindow(self._recorder_hwnd)
            time.sleep(0.1)
            win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
            time.sleep(0.01)
            win32api.keybd_event(ord('S'), 0, 0, 0)
            time.sleep(0.01)
            win32api.keybd_event(ord('S'), 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
            time.sleep(0.1)
            try:
                if current_hwnd and win32gui.IsWindow(current_hwnd):
                    win32gui.SetForegroundWindow(current_hwnd)
            except:
                pass
            self.log.info("Kayit baslatildi (Ctrl+S)")
            return True
        except Exception as e:
            self.log.error(f"Kayit baslatma hatasi: {e}")
            return False

    def stop_recording(self):
        """Kayit durdur - ayni Ctrl+S toggle"""
        if win32gui is None:
            return False
        if not self._recorder_hwnd or not win32gui.IsWindow(self._recorder_hwnd):
            if not self._find_recorder():
                return False
        try:
            current_hwnd = win32gui.GetForegroundWindow()
            win32gui.SetForegroundWindow(self._recorder_hwnd)
            time.sleep(0.1)
            win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
            time.sleep(0.01)
            win32api.keybd_event(ord('S'), 0, 0, 0)
            time.sleep(0.01)
            win32api.keybd_event(ord('S'), 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
            time.sleep(0.1)
            try:
                if current_hwnd and win32gui.IsWindow(current_hwnd):
                    win32gui.SetForegroundWindow(current_hwnd)
            except:
                pass
            self.log.info("Kayit durduruldu (Ctrl+S)")
            return True
        except Exception as e:
            self.log.error(f"Kayit durdurma hatasi: {e}")
            return False

    # ── Trigger ────────────────────────────────────────────────────────────

    def trigger(self) -> bool:
        """
        Avisoft playlist'te bir sonraki sesi çal.
        Playlist penceresindeki Start butonuna BM_CLICK gönderir.
        """
        if win32gui is None:
            self.log.error("pywin32 yüklü değil")
            return False

        if not self._hwnd_playlist or not win32gui.IsWindow(self._hwnd_playlist):
            if not self._find_window():
                return False
            if not self._hwnd_playlist:
                self.log.error("Playlist penceresi bulunamadı")
                return False

        BM_CLICK = 0x00F5
        btn = self._find_start_button()
        if not btn or not win32gui.IsWindow(btn):
            self.log.error("Playlist Start butonu bulunamadı — list_children() çalıştır")
            return False

        try:
            win32gui.SendMessage(btn, BM_CLICK, 0, 0)
            self.log.info("Avisoft trigger gönderildi (BM_CLICK → Start butonu)")
            return True
        except Exception as e:
            self.log.error(f"Avisoft trigger hatası: {e}")
            return False
