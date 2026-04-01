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

    # ── Kayıt başlatma ─────────────────────────────────────────────────────

    def start_recording(self) -> bool:
        """
        Avisoft Recorder ana penceresine Shift+Space göndererek kaydı başlatır.
        Playlist trigger'ı etkilemez.
        """
        if win32gui is None:
            self.log.error("pywin32 yüklü değil")
            return False

        if not self._hwnd or not win32gui.IsWindow(self._hwnd):
            if not self._find_window():
                return False
            if not self._hwnd:
                self.log.error("Avisoft Recorder ana penceresi bulunamadı")
                return False

        target = self._hwnd
        user32 = ctypes.windll.user32
        try:
            current_tid  = win32api.GetCurrentThreadId()
            target_tid, _= win32process.GetWindowThreadProcessId(target)
            prev_hwnd    = win32gui.GetForegroundWindow()

            attached = False
            if current_tid != target_tid:
                try:
                    win32process.AttachThreadInput(current_tid, target_tid, True)
                    attached = True
                except Exception:
                    pass

            try:
                user32.ShowWindow(target, 9)       # SW_RESTORE
                user32.BringWindowToTop(target)
                user32.SetForegroundWindow(target)
                user32.SetActiveWindow(target)
                time.sleep(0.15)

                _send_key(win32con.VK_SHIFT)
                _send_key(win32con.VK_SPACE)
                _send_key(win32con.VK_SPACE, key_up=True)
                _send_key(win32con.VK_SHIFT, key_up=True)
                time.sleep(0.05)

                # PostMessage ile de gönder (bazı Avisoft sürümlerinde daha güvenilir)
                def _lp(scan, key_up=False):
                    lp = 1 | (scan << 16)
                    if key_up:
                        lp |= (1 << 30) | (1 << 31)
                    return lp
                ss = win32api.MapVirtualKey(win32con.VK_SHIFT, 0)
                sp = win32api.MapVirtualKey(win32con.VK_SPACE, 0)
                win32gui.PostMessage(target, win32con.WM_KEYDOWN, win32con.VK_SHIFT, _lp(ss))
                win32gui.PostMessage(target, win32con.WM_KEYDOWN, win32con.VK_SPACE, _lp(sp))
                win32gui.PostMessage(target, win32con.WM_CHAR,    0x20,              _lp(sp))
                win32gui.PostMessage(target, win32con.WM_KEYUP,   win32con.VK_SPACE, _lp(sp, True))
                win32gui.PostMessage(target, win32con.WM_KEYUP,   win32con.VK_SHIFT, _lp(ss, True))

            finally:
                if attached:
                    win32process.AttachThreadInput(current_tid, target_tid, False)
                time.sleep(0.05)
                try:
                    if prev_hwnd and win32gui.IsWindow(prev_hwnd):
                        user32.SetForegroundWindow(prev_hwnd)
                except Exception:
                    pass

            self.log.info("Avisoft kayıt başlatıldı (Shift+Space → Recorder)")
            return True

        except Exception as e:
            self.log.error(f"Avisoft kayıt başlatma hatası: {e}")
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
