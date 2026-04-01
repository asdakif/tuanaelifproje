"""
Operant Koşullanma — Ana Arayüz
DS+ / DS− Discriminative Stimulus Paradigm
Boğaziçi Üniversitesi Davranışsal Nörobilim Laboratuvarı
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import logging
import os
import threading
import time
import webbrowser
from datetime import datetime

import config
from operant_box import OperantBox
from experiment import Experiment, State, DSType, TrialResult


# ── Logging kurulumu ──────────────────────────────────────────────────────────

class TextHandler(logging.Handler):
    def __init__(self, widget: scrolledtext.ScrolledText):
        super().__init__()
        self.widget = widget

    def emit(self, record):
        msg = self.format(record)
        def _append():
            self.widget.configure(state="normal")
            tag = ("ERROR" if record.levelno >= logging.ERROR else
                   "WARN"  if record.levelno >= logging.WARNING else
                   "INFO"  if record.levelno >= logging.INFO else "DEBUG")
            self.widget.insert(tk.END, msg + "\n", tag)
            self.widget.see(tk.END)
            self.widget.configure(state="disabled")
        self.widget.after(0, _append)


# ── Ana Pencere ───────────────────────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Operant Box — DS+/DS− Paradigm | Boğaziçi Üniversitesi")
        self.resizable(True, True)
        self._build_ui()
        self._setup_logging()
        self.box = None
        self.exp = None
        self._max_consec   = 3
        self._animal_queue: list[str] = []
        self._animal_index: int       = 0
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI inşa ───────────────────────────────────────────────────────────────

    def _build_ui(self):
        PAD = dict(padx=8, pady=3)

        # Ana çerçeve: sol (ayarlar) + sağ (durum + log)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)

        # Sol panel — scrollable
        left_outer = ttk.Frame(self)
        left_outer.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        left_outer.rowconfigure(0, weight=1)
        left_outer.columnconfigure(0, weight=1)

        left_canvas = tk.Canvas(left_outer, highlightthickness=0)
        left_canvas.grid(row=0, column=0, sticky="nsew")

        left_scroll = ttk.Scrollbar(left_outer, orient="vertical", command=left_canvas.yview)
        left_scroll.grid(row=0, column=1, sticky="ns")
        left_canvas.configure(yscrollcommand=left_scroll.set)

        left = ttk.Frame(left_canvas)
        left_window = left_canvas.create_window((0, 0), window=left, anchor="nw")

        def _on_left_configure(event):
            left_canvas.configure(scrollregion=left_canvas.bbox("all"))
        def _on_canvas_resize(event):
            left_canvas.itemconfig(left_window, width=event.width)

        left.bind("<Configure>", _on_left_configure)
        left_canvas.bind("<Configure>", _on_canvas_resize)

        def _on_mousewheel(event):
            left_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        left_canvas.bind_all("<MouseWheel>", _on_mousewheel)

        right = ttk.Frame(self)
        right.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)

        # ════════════════════════════════
        # SOL PANEL
        # ════════════════════════════════

        # ── Hayvan & Oturum ──────────────
        sess_frame = ttk.LabelFrame(left, text="Oturum Bilgisi")
        sess_frame.pack(fill="x", pady=4)

        ttk.Label(sess_frame, text="Hayvan Listesi\n(her satıra bir ID):",
                  justify="left").grid(row=0, column=0, sticky="nw", **PAD)
        self.txt_animal_list = tk.Text(sess_frame, width=16, height=5, font=("Courier", 10))
        self.txt_animal_list.grid(row=0, column=1, **PAD)

        # Sıra göstergesi
        self.lbl_animal_queue = ttk.Label(sess_frame, text="", foreground="#1565C0",
                                          font=("Helvetica", 9, "italic"))
        self.lbl_animal_queue.grid(row=1, column=0, columnspan=2, sticky="w", padx=8)

        ttk.Label(sess_frame, text="Avisoft DOUT\nport (opsiyonel):",
                  justify="left").grid(row=2, column=0, sticky="w", **PAD)
        self.var_dout_port = tk.StringVar(value=config.AVISOFT_DOUT_PORT)
        ttk.Entry(sess_frame, textvariable=self.var_dout_port, width=10).grid(row=2, column=1, **PAD)

        # ── Bağlantı ─────────────────────
        conn_frame = ttk.LabelFrame(left, text="Bağlantı Ayarları")
        conn_frame.pack(fill="x", pady=4)

        ttk.Label(conn_frame, text="Kutu Portu:").grid(row=0, column=0, sticky="w", **PAD)
        self.var_box_port = tk.StringVar(value=config.BOX_PORT)
        ttk.Entry(conn_frame, textvariable=self.var_box_port, width=10).grid(row=0, column=1, **PAD)


        self.var_simulated = tk.BooleanVar(value=False)
        ttk.Checkbutton(conn_frame, text="Simülasyon modu",
                        variable=self.var_simulated).grid(row=1, column=0, columnspan=2, sticky="w", **PAD)

        self.btn_connect = ttk.Button(conn_frame, text="Bağlan", command=self._connect)
        self.btn_connect.grid(row=2, column=0, columnspan=2, pady=6)

        # ── Deney Parametreleri ───────────
        param_frame = ttk.LabelFrame(left, text="Deney Parametreleri")
        param_frame.pack(fill="x", pady=4)

        params = [
            ("Trial sayısı:",        "var_num_trials",   str(config.NUM_TRIALS)),
            ("DS+ oranı (0-1):",     "var_ds_ratio",     str(config.DS_PLUS_RATIO)),
            ("ITI min (s):",         "var_iti_min",       str(config.ITI_MIN_S)),
            ("ITI max (s):",         "var_iti_max",       str(config.ITI_MAX_S)),
            ("DS süresi (s):",       "var_ds_dur",        str(config.DS_DURATION_S)),
            ("Yanıt penceresi (s):", "var_resp_win",      str(config.RESPONSE_WINDOW_S)),
            ("Şok süresi (s):",      "var_shock_dur",     str(config.SHOCK_DURATION_S)),
            ("Şok akımı (mA):",      "var_shock_ma",      str(config.SHOCK_CURRENT_MA)),
            ("Su pulse sayısı:",     "var_water_pulses",  str(config.WATER_PULSES)),
            ("Lick penceresi (s):",  "var_lick_window",   str(config.LICK_WINDOW_S)),
            ("DS+ TTL (ms):",        "var_ttl_plus_dur",  str(config.BNC_DS_PLUS_DURATION)),
            ("DS− TTL (ms):",        "var_ttl_minus_dur", str(config.BNC_DS_MINUS_DURATION)),
            ("TTL voltaj (V):",      "var_ttl_voltage",   str(config.BNC_DS_PLUS_VOLTAGE)),
            ("Max üst üste:",        "var_max_consec",        "3"),
            ("Kriter Hit Rate:",     "var_criterion_hit",     str(config.CRITERION_HIT_RATE)),
            ("Kriter d':",           "var_criterion_dprime",  str(config.CRITERION_DPRIME)),
        ]
        for i, (label, var_name, default) in enumerate(params):
            ttk.Label(param_frame, text=label).grid(row=i, column=0, sticky="w", **PAD)
            var = tk.StringVar(value=default)
            setattr(self, var_name, var)
            ttk.Entry(param_frame, textvariable=var, width=8).grid(row=i, column=1, **PAD)

        # ── Lever Ayarları ────────────────
        lev_frame = ttk.LabelFrame(left, text="Lever Ayarları")
        lev_frame.pack(fill="x", pady=4)

        ttk.Label(lev_frame, text="Aktif lever:").grid(row=0, column=0, sticky="w", **PAD)
        self.var_lever_side = tk.StringVar(value="Sol (0x01)")
        ttk.Combobox(lev_frame, textvariable=self.var_lever_side,
                     values=["Sol (0x01)", "Sağ (0x02)"],
                     width=14, state="readonly").grid(row=0, column=1, **PAD)

        self.var_lever_on_ds = tk.BooleanVar(value=config.LEVER_EXTEND_ON_DS)
        ttk.Checkbutton(lev_frame, text="DS başlayınca lever çıksın",
                        variable=self.var_lever_on_ds).grid(row=1, column=0, columnspan=2, sticky="w", **PAD)

        ttk.Label(lev_frame, text="Yanıt gecikmesi (s):").grid(row=2, column=0, sticky="w", **PAD)
        self.var_resp_delay = tk.StringVar(value=str(config.RESPONSE_DELAY_S))
        ttk.Entry(lev_frame, textvariable=self.var_resp_delay, width=8).grid(row=2, column=1, **PAD)

        # ── Outcome Ayarları ──────────────
        out_frame = ttk.LabelFrame(left, text="Outcome Ayarları")
        out_frame.pack(fill="x", pady=4)

        ttk.Label(out_frame, text="DS+ outcome:").grid(row=0, column=0, sticky="w", **PAD)
        self.var_ds_plus_outcome = tk.StringVar(value=config.DS_PLUS_OUTCOME)
        ttk.Combobox(out_frame, textvariable=self.var_ds_plus_outcome,
                     values=["reward", "punishment"], width=12, state="readonly").grid(row=0, column=1, **PAD)

        ttk.Label(out_frame, text="DS− outcome:").grid(row=1, column=0, sticky="w", **PAD)
        self.var_ds_minus_outcome = tk.StringVar(value=config.DS_MINUS_OUTCOME)
        ttk.Combobox(out_frame, textvariable=self.var_ds_minus_outcome,
                     values=["reward", "punishment"], width=12, state="readonly").grid(row=1, column=1, **PAD)


        # ── Avisoft Playlist ──────────────
        av_frame = ttk.LabelFrame(left, text="Avisoft Playlist")
        av_frame.pack(fill="x", pady=4)

        ttk.Label(av_frame, text="DS+ .wav:").grid(row=0, column=0, sticky="w", **PAD)
        self.var_ds_plus_wav = tk.StringVar(value=config.DS_PLUS_WAV)
        ttk.Entry(av_frame, textvariable=self.var_ds_plus_wav, width=26).grid(row=0, column=1, **PAD)
        ttk.Button(av_frame, text="Gözat…", width=7,
                   command=lambda: self._browse_wav(self.var_ds_plus_wav)).grid(row=0, column=2, **PAD)

        ttk.Label(av_frame, text="DS+ .wav dosyaları:").grid(row=1, column=0, sticky="w", **PAD)
        self.ds_plus_wav_list: list[str] = list(config.DS_PLUS_WAV_LIST)
        self._lb_ds_plus = tk.Listbox(av_frame, height=4, width=30)
        self._lb_ds_plus.grid(row=2, column=0, columnspan=2, sticky="ew", **PAD)
        for p in self.ds_plus_wav_list:
            self._lb_ds_plus.insert(tk.END, p)
        _btn_plus_frame = ttk.Frame(av_frame)
        _btn_plus_frame.grid(row=2, column=2, sticky="n", **PAD)
        ttk.Button(_btn_plus_frame, text="Ekle…",
                   command=lambda: self._add_wavs(self._lb_ds_plus, self.ds_plus_wav_list)
                   ).pack(fill="x")
        ttk.Button(_btn_plus_frame, text="Temizle",
                   command=lambda: self._clear_wavs(self._lb_ds_plus, self.ds_plus_wav_list)
                   ).pack(fill="x")

        ttk.Label(av_frame, text="DS− .wav:").grid(row=3, column=0, sticky="w", **PAD)
        self.var_ds_minus_wav = tk.StringVar(value=config.DS_MINUS_WAV)
        ttk.Entry(av_frame, textvariable=self.var_ds_minus_wav, width=26).grid(row=3, column=1, **PAD)
        ttk.Button(av_frame, text="Gözat…", width=7,
                   command=lambda: self._browse_wav(self.var_ds_minus_wav)).grid(row=3, column=2, **PAD)

        ttk.Label(av_frame, text="DS− .wav dosyaları:").grid(row=4, column=0, sticky="w", **PAD)
        self.ds_minus_wav_list: list[str] = list(config.DS_MINUS_WAV_LIST)
        self._lb_ds_minus = tk.Listbox(av_frame, height=4, width=30)
        self._lb_ds_minus.grid(row=5, column=0, columnspan=2, sticky="ew", **PAD)
        for p in self.ds_minus_wav_list:
            self._lb_ds_minus.insert(tk.END, p)
        _btn_minus_frame = ttk.Frame(av_frame)
        _btn_minus_frame.grid(row=5, column=2, sticky="n", **PAD)
        ttk.Button(_btn_minus_frame, text="Ekle…",
                   command=lambda: self._add_wavs(self._lb_ds_minus, self.ds_minus_wav_list)
                   ).pack(fill="x")
        ttk.Button(_btn_minus_frame, text="Temizle",
                   command=lambda: self._clear_wavs(self._lb_ds_minus, self.ds_minus_wav_list)
                   ).pack(fill="x")

        ttk.Label(av_frame, text="Playlist:").grid(row=6, column=0, sticky="w", **PAD)
        self.var_playlist = tk.StringVar(value=config.AVISOFT_PLAYLIST)
        ttk.Entry(av_frame, textvariable=self.var_playlist, width=26).grid(row=6, column=1, **PAD)
        ttk.Button(av_frame, text="Gözat…", width=7,
                   command=lambda: self._browse_playlist(self.var_playlist)).grid(row=6, column=2, **PAD)

        ttk.Label(av_frame, text="Playback exe:").grid(row=7, column=0, sticky="w", **PAD)
        self.var_avisoft_exe = tk.StringVar(value=config.AVISOFT_EXE)
        ttk.Entry(av_frame, textvariable=self.var_avisoft_exe, width=26).grid(row=7, column=1, **PAD)
        ttk.Button(av_frame, text="Gözat…", width=7,
                   command=lambda: self._browse_exe(self.var_avisoft_exe)).grid(row=7, column=2, **PAD)

        ttk.Label(av_frame, text="Playback config:").grid(row=8, column=0, sticky="w", **PAD)
        self.var_playback_config = tk.StringVar(value=config.AVISOFT_PLAYBACK_CONFIG)
        ttk.Entry(av_frame, textvariable=self.var_playback_config, width=26).grid(row=8, column=1, **PAD)
        ttk.Button(av_frame, text="Gözat…", width=7,
                   command=lambda: self._browse_ini(self.var_playback_config)).grid(row=8, column=2, **PAD)

        ttk.Label(av_frame, text="Record exe:").grid(row=9, column=0, sticky="w", **PAD)
        self.var_record_exe = tk.StringVar(value=config.AVISOFT_RECORD_EXE)
        ttk.Entry(av_frame, textvariable=self.var_record_exe, width=26).grid(row=9, column=1, **PAD)
        ttk.Button(av_frame, text="Gözat…", width=7,
                   command=lambda: self._browse_exe(self.var_record_exe)).grid(row=9, column=2, **PAD)

        ttk.Label(av_frame, text="Record config:").grid(row=10, column=0, sticky="w", **PAD)
        self.var_record_config = tk.StringVar(value=config.AVISOFT_RECORD_CONFIG)
        ttk.Entry(av_frame, textvariable=self.var_record_config, width=26).grid(row=10, column=1, **PAD)
        ttk.Button(av_frame, text="Gözat…", width=7,
                   command=lambda: self._browse_ini(self.var_record_config)).grid(row=10, column=2, **PAD)

        ttk.Label(av_frame, text="Açılış gecikmesi (s):").grid(row=11, column=0, sticky="w", **PAD)
        self.var_avisoft_delay = tk.StringVar(value=str(config.AVISOFT_LAUNCH_DELAY_S))
        ttk.Entry(av_frame, textvariable=self.var_avisoft_delay, width=6).grid(row=11, column=1, sticky="w", **PAD)

        self.btn_gen_playlist = ttk.Button(av_frame, text="Playlist Oluştur",
                                           command=self._gen_playlist, state="disabled")
        self.btn_gen_playlist.grid(row=12, column=0, columnspan=3, sticky="ew", padx=8, pady=4)

        # ── Kontrol ──────────────────────
        ctrl_frame = ttk.LabelFrame(left, text="Kontrol")
        ctrl_frame.pack(fill="x", pady=4)

        self.btn_start = ttk.Button(ctrl_frame, text="▶  Başlat", command=self._start, state="disabled")
        self.btn_start.pack(fill="x", padx=8, pady=2)

        self.btn_stop = ttk.Button(ctrl_frame, text="⏹  Durdur", command=self._stop, state="disabled")
        self.btn_stop.pack(fill="x", padx=8, pady=2)

        ttk.Button(ctrl_frame, text="Rapor Oluştur", command=self._generate_report).pack(fill="x", padx=8, pady=2)

        # ── Simülasyon ───────────────────
        sim_frame = ttk.LabelFrame(left, text="Simülasyon Kontrolleri")
        sim_frame.pack(fill="x", pady=4)

        row2 = ttk.Frame(sim_frame); row2.pack(fill="x", padx=8, pady=2)
        self.btn_lever = ttk.Button(row2, text="Lever Bas", command=self._sim_lever, state="disabled")
        self.btn_lick  = ttk.Button(row2, text="Lick",      command=self._sim_lick,  state="disabled")
        self.btn_lever.pack(side="left", expand=True, fill="x", padx=2)
        self.btn_lick.pack(side="left", expand=True, fill="x", padx=2)

        # ── Donanım Testi ─────────────────
        hw_frame = ttk.LabelFrame(left, text="Donanım Testi")
        hw_frame.pack(fill="x", pady=4)

        ttk.Label(hw_frame, text="Bağlan'dan sonra kullan. Deney sırasında kullanma.",
                  foreground="gray", wraplength=220).pack(padx=8, pady=2, anchor="w")

        r1 = ttk.Frame(hw_frame); r1.pack(fill="x", padx=8, pady=2)
        self.btn_hw_lever_ext = ttk.Button(r1, text="Lever Çıkar",  command=self._hw_lever_extend, state="disabled")
        self.btn_hw_lever_ret = ttk.Button(r1, text="Lever Geri Al", command=self._hw_lever_retract, state="disabled")
        self.btn_hw_lever_ext.pack(side="left", expand=True, fill="x", padx=2)
        self.btn_hw_lever_ret.pack(side="left", expand=True, fill="x", padx=2)

        r2 = ttk.Frame(hw_frame); r2.pack(fill="x", padx=8, pady=2)
        self.btn_hw_water = ttk.Button(r2, text="Su Ver", command=self._hw_water, state="disabled")
        self.btn_hw_shock = ttk.Button(r2, text="Şok Ver", command=self._hw_shock, state="disabled")
        self.btn_hw_water.pack(side="left", expand=True, fill="x", padx=2)
        self.btn_hw_shock.pack(side="left", expand=True, fill="x", padx=2)

        r2b = ttk.Frame(hw_frame); r2b.pack(fill="x", padx=8, pady=2)
        ttk.Label(r2b, text="Şok süresi (sn):").pack(side="left", padx=4)
        self._hw_shock_dur = tk.DoubleVar(value=config.SHOCK_DURATION_S)
        ttk.Spinbox(r2b, from_=0.1, to=10.0, increment=0.1, textvariable=self._hw_shock_dur, width=6).pack(side="left")

        r3b = ttk.Frame(hw_frame); r3b.pack(fill="x", padx=8, pady=2)
        self.btn_hw_house_on  = ttk.Button(r3b, text="House Light Yak",    command=self._hw_house_on,  state="disabled")
        self.btn_hw_house_off = ttk.Button(r3b, text="House Light Söndür", command=self._hw_house_off, state="disabled")
        self.btn_hw_house_on.pack(side="left", expand=True, fill="x", padx=2)
        self.btn_hw_house_off.pack(side="left", expand=True, fill="x", padx=2)

        r4 = ttk.Frame(hw_frame); r4.pack(fill="x", padx=8, pady=2)
        self.btn_hw_bnc = ttk.Button(r4, text="BNC TTL Gönder (100ms)", command=self._hw_bnc, state="disabled")
        self.btn_hw_bnc.pack(fill="x", padx=2)

        r5 = ttk.Frame(hw_frame); r5.pack(fill="x", padx=8, pady=2)
        self.btn_hw_av_test = ttk.Button(r5, text="Avisoft Trigger Test",
                                         command=self._hw_avisoft_trigger, state="disabled")
        self.btn_hw_av_list = ttk.Button(r5, text="Pencere Listesi (Log)",
                                         command=self._hw_avisoft_list_windows, state="disabled")
        self.btn_hw_av_test.pack(side="left", expand=True, fill="x", padx=2)
        self.btn_hw_av_list.pack(side="left", expand=True, fill="x", padx=2)

        self._hw_buttons = [
            self.btn_hw_lever_ext, self.btn_hw_lever_ret,
            self.btn_hw_water, self.btn_hw_shock,
            self.btn_hw_house_on, self.btn_hw_house_off,
            self.btn_hw_bnc,
            self.btn_hw_av_test, self.btn_hw_av_list,
        ]

        # ════════════════════════════════
        # SAĞ PANEL
        # ════════════════════════════════

        # ── DS Göstergesi ────────────────
        ind_frame = ttk.Frame(right)
        ind_frame.pack(fill="x", pady=4)

        self.canvas_ds = tk.Canvas(ind_frame, width=80, height=80, bg="#1a1a1a",
                                   highlightthickness=0)
        self.canvas_ds.pack(side="left", padx=8)
        self.ds_circle = self.canvas_ds.create_oval(8, 8, 72, 72, fill="gray", outline="")

        info_col = ttk.Frame(ind_frame)
        info_col.pack(side="left", fill="x", expand=True)
        self.lbl_state = self._status_row(info_col, "Durum:",   "HAZIR", 0)
        self.lbl_trial = self._status_row(info_col, "Trial:",   "—",     1)
        self.lbl_ds    = self._status_row(info_col, "DS Tipi:", "—",     2)

        # ── Sonuç Tablosu ────────────────
        res_frame = ttk.LabelFrame(right, text="Trial Sonuçları")
        res_frame.pack(fill="x", pady=4)

        self.lbl_reward  = self._status_row(res_frame, "Ödül (rewarded):",      "0", 0)
        self.lbl_punish  = self._status_row(res_frame, "Ceza (punished):",      "0", 1)
        self.lbl_omit    = self._status_row(res_frame, "Omission (DS+↓):",      "0", 2)
        self.lbl_cr      = self._status_row(res_frame, "Correct Rej. (DS−↓):", "0", 3)

        # ── Diskriminasyon Metrikleri ─────
        disc_frame = ttk.LabelFrame(right, text="Diskriminasyon (canlı)")
        disc_frame.pack(fill="x", pady=4)

        self.lbl_hit_rate = self._status_row(disc_frame, "Hit Rate (DS+):",  "—", 0)
        self.lbl_cr_rate  = self._status_row(disc_frame, "CR Rate (DS−):",   "—", 1)
        self.lbl_dprime   = self._status_row(disc_frame, "d' (d-prime):",    "—", 2)

        # Progress bar d'
        self.dprime_bar = ttk.Progressbar(disc_frame, maximum=4.0, length=200)
        self.dprime_bar.grid(row=3, column=0, columnspan=2, padx=8, pady=4, sticky="ew")

        # ── Lick & ITI ───────────────────
        misc_frame = ttk.LabelFrame(right, text="Lick & ITI")
        misc_frame.pack(fill="x", pady=4)

        self.lbl_lick_trial  = self._status_row(misc_frame, "Lick (bu trial):",   "0", 0)
        self.lbl_lick_total  = self._status_row(misc_frame, "Lick (toplam):",      "0", 1)
        self.lbl_iti_trial   = self._status_row(misc_frame, "ITI press (trial):",  "0", 2)
        self.lbl_iti_total   = self._status_row(misc_frame, "ITI press (toplam):", "0", 3)
        self.lbl_logf        = self._status_row(misc_frame, "Log dosyası:",         "—", 4)

        # ── Log ──────────────────────────
        log_frame = ttk.LabelFrame(right, text="Log")
        log_frame.pack(fill="both", expand=True, pady=4)

        self.log_text = scrolledtext.ScrolledText(log_frame, width=58, height=20,
                                                   state="disabled", font=("Courier", 9))
        self.log_text.pack(fill="both", expand=True, padx=4, pady=4)
        self.log_text.tag_config("ERROR", foreground="#ff5555")
        self.log_text.tag_config("WARN",  foreground="#ffb86c")
        self.log_text.tag_config("INFO",  foreground="#f8f8f2")
        self.log_text.tag_config("DEBUG", foreground="#6272a4")
        self.log_text.configure(background="#282a36", foreground="#f8f8f2")

        ttk.Button(log_frame, text="Temizle",
                   command=lambda: [self.log_text.configure(state="normal"),
                                    self.log_text.delete(1.0, tk.END),
                                    self.log_text.configure(state="disabled")]
                   ).pack(anchor="e", padx=4, pady=2)

    def _status_row(self, parent, label: str, default: str, row: int) -> ttk.Label:
        ttk.Label(parent, text=label, width=22, anchor="w").grid(
            row=row, column=0, sticky="w", padx=6, pady=1)
        var = tk.StringVar(value=default)
        lbl = ttk.Label(parent, textvariable=var, width=14, anchor="w",
                        font=("Helvetica", 10, "bold"))
        lbl.grid(row=row, column=1, sticky="w", padx=4, pady=1)
        lbl._var = var
        return lbl

    def _setup_logging(self):
        fmt = logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s",
                                datefmt="%H:%M:%S")
        handler = TextHandler(self.log_text)
        handler.setFormatter(fmt)
        root_log = logging.getLogger()
        root_log.setLevel(logging.DEBUG)
        root_log.addHandler(handler)
        os.makedirs(config.LOG_DIR, exist_ok=True)
        fh = logging.FileHandler(
            os.path.join(config.LOG_DIR, f"app_{datetime.now().strftime('%Y%m%d')}.log"),
            encoding="utf-8")
        fh.setFormatter(fmt)
        root_log.addHandler(fh)

    # ── Bağlantı ──────────────────────────────────────────────────────────────

    def _connect(self):
        simulated = self.var_simulated.get()
        box_port  = self.var_box_port.get().strip()

        self.box = OperantBox(box_port, config.CHANNEL, simulated=simulated)

        if not self.box.connect():
            messagebox.showerror("Hata", f"Kutu bağlantısı başarısız: {box_port}")
            return

        self.exp = Experiment(self.box)
        self.exp.on_state_change(self._on_state_change)
        self.exp.on_trial_end(self._on_trial_end)
        self.exp.on_lick_update(self._on_lick_update)
        self.exp.on_discrimination_update(self._on_disc_update)
        self.exp.on_iti_press(self._on_iti_press)

        self.btn_connect.configure(state="disabled")
        self.btn_start.configure(state="normal")
        self.btn_gen_playlist.configure(state="normal")
        if simulated:
            self.btn_lever.configure(state="normal")
            self.btn_lick.configure(state="normal")
        for b in self._hw_buttons:
            b.configure(state="normal")

        logging.getLogger("App").info("Bağlantı kuruldu.")

    # ── Parametreler & Başlat ──────────────────────────────────────────────────

    def _browse_exe(self, var: tk.StringVar):
        path = filedialog.askopenfilename(
            title="Avisoft çalıştırılabilir dosyasını seç",
            filetypes=[("Çalıştırılabilir", "*.exe"), ("Tüm dosyalar", "*.*")]
        )
        if path:
            var.set(path)

    def _browse_ini(self, var: tk.StringVar):
        path = filedialog.askopenfilename(
            title="Avisoft config dosyasını seç",
            filetypes=[("Config dosyası", "*.ini"), ("Tüm dosyalar", "*.*")]
        )
        if path:
            var.set(path)

    def _browse_wav(self, var: tk.StringVar):
        path = filedialog.askopenfilename(
            title="WAV dosyasını seç",
            filetypes=[("WAV dosyaları", "*.wav"), ("Tüm dosyalar", "*.*")]
        )
        if path:
            var.set(path)

    def _add_wavs(self, lb: tk.Listbox, lst: list):
        paths = filedialog.askopenfilenames(
            title="WAV dosyalarını seç",
            filetypes=[("WAV dosyaları", "*.wav"), ("Tüm dosyalar", "*.*")]
        )
        for p in paths:
            lst.append(p)
            lb.insert(tk.END, p)

    def _clear_wavs(self, lb: tk.Listbox, lst: list):
        lst.clear()
        lb.delete(0, tk.END)

    def _browse_playlist(self, var: tk.StringVar):
        path = filedialog.asksaveasfilename(
            title="Playlist kayıt yeri",
            defaultextension=".txt",
            filetypes=[("Metin dosyası", "*.txt"), ("Tüm dosyalar", "*.*")]
        )
        if path:
            var.set(path)

    def _apply_params(self) -> bool:
        try:
            config.NUM_TRIALS            = int(self.var_num_trials.get())
            config.DS_PLUS_RATIO         = float(self.var_ds_ratio.get())
            config.ITI_MIN_S             = float(self.var_iti_min.get())
            config.ITI_MAX_S             = float(self.var_iti_max.get())
            config.DS_DURATION_S         = float(self.var_ds_dur.get())
            config.RESPONSE_WINDOW_S     = float(self.var_resp_win.get())
            config.SHOCK_DURATION_S      = float(self.var_shock_dur.get())
            config.SHOCK_CURRENT_MA      = float(self.var_shock_ma.get())
            config.WATER_PULSES          = int(self.var_water_pulses.get())
            config.LICK_WINDOW_S         = float(self.var_lick_window.get())
            config.BNC_DS_PLUS_DURATION  = int(self.var_ttl_plus_dur.get())
            config.BNC_DS_MINUS_DURATION = int(self.var_ttl_minus_dur.get())
            config.BNC_DS_PLUS_VOLTAGE   = float(self.var_ttl_voltage.get())
            config.BNC_DS_MINUS_VOLTAGE  = float(self.var_ttl_voltage.get())
            config.LEVER_SIDE            = 0x01 if "Sol" in self.var_lever_side.get() else 0x02
            config.LEVER_EXTEND_ON_DS    = self.var_lever_on_ds.get()
            config.RESPONSE_DELAY_S      = float(self.var_resp_delay.get())
            config.DS_PLUS_OUTCOME       = self.var_ds_plus_outcome.get()
            config.DS_MINUS_OUTCOME      = self.var_ds_minus_outcome.get()
            config.DS_PLUS_WAV           = self.var_ds_plus_wav.get().strip()
            config.DS_MINUS_WAV          = self.var_ds_minus_wav.get().strip()
            if self.ds_plus_wav_list:
                config.DS_PLUS_WAV_LIST  = list(self.ds_plus_wav_list)
            if self.ds_minus_wav_list:
                config.DS_MINUS_WAV_LIST = list(self.ds_minus_wav_list)
            config.AVISOFT_PLAYLIST          = self.var_playlist.get().strip()
            config.AVISOFT_EXE               = self.var_avisoft_exe.get().strip()
            config.AVISOFT_PLAYBACK_CONFIG   = self.var_playback_config.get().strip()
            config.AVISOFT_RECORD_EXE        = self.var_record_exe.get().strip()
            config.AVISOFT_RECORD_CONFIG     = self.var_record_config.get().strip()
            config.AVISOFT_LAUNCH_DELAY_S    = float(self.var_avisoft_delay.get())
            config.AVISOFT_DOUT_PORT         = self.var_dout_port.get().strip()
            self._max_consec             = int(self.var_max_consec.get())
            config.CRITERION_HIT_RATE    = float(self.var_criterion_hit.get())
            config.CRITERION_DPRIME      = float(self.var_criterion_dprime.get())
            return True
        except ValueError as e:
            messagebox.showerror("Parametre Hatası", str(e))
            return False

    def _start(self):
        if not self.exp or not self._apply_params():
            return
        # Listeyi parse et
        raw = self.txt_animal_list.get("1.0", tk.END)
        ids = [line.strip() for line in raw.splitlines() if line.strip()]
        if not ids:
            messagebox.showwarning("Hayvan Listesi", "Lütfen en az bir hayvan ID girin!")
            return
        self._animal_queue = ids
        self._animal_index = 0
        self._start_next_animal()

    def _start_next_animal(self):
        animal_id = self._animal_queue[self._animal_index]
        total     = len(self._animal_queue)
        self.lbl_animal_queue.config(
            text=f"Sıra: {self._animal_index + 1}/{total} — Şu an: {animal_id}"
        )
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        logging.getLogger("App").info(
            f"Hayvan {self._animal_index + 1}/{total}: {animal_id} başlıyor"
        )
        self.exp.start(self._max_consec, animal_id=animal_id)

    def _stop(self):
        if self.exp:
            self.exp.stop()
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")

    # ── Simülasyon ────────────────────────────────────────────────────────────

    def _gen_playlist(self):
        if not self.exp or not self._apply_params():
            return
        path = self.exp.prepare_playlist(self._max_consec)
        messagebox.showinfo("Playlist Oluşturuldu", f"Playlist kaydedildi:\n{path}")

    def _sim_lever(self):
        if self.box: self.box.simulate_lever_press('left')

    def _sim_lick(self):
        if self.box: self.box.simulate_lick('left')

    # ── Deney callback'leri ───────────────────────────────────────────────────

    def _on_state_change(self, state: State, trial_num: int, ds: object):
        state_labels = {
            State.IDLE:        "HAZIR",
            State.ITI:         "ITI",
            State.DS_ON:       "DS SUNULUYOR",
            State.RESPONSE:    "YANIT BEKLENİYOR",
            State.OUTCOME:     "OUTCOME",
            State.SESSION_END: "TAMAMLANDI",
        }
        def _update():
            self.lbl_state._var.set(state_labels.get(state, "?"))
            self.lbl_trial._var.set(
                f"{trial_num} / {config.NUM_TRIALS}" if trial_num else "—")

            if ds is None:
                self.lbl_ds._var.set("—")
                self.canvas_ds.itemconfig(self.ds_circle, fill="gray")
            elif ds == DSType.PLUS:
                self.lbl_ds._var.set("DS+")
                self.canvas_ds.itemconfig(self.ds_circle, fill="#00e676")
            else:
                self.lbl_ds._var.set("DS−")
                self.canvas_ds.itemconfig(self.ds_circle, fill="#ff1744")

            if state == State.SESSION_END:
                self.btn_stop.configure(state="disabled")
                hr, cr, dp = self.exp.discrimination_metrics()
                self._show_session_end_dialog(hr, cr, dp)
        self.after(0, _update)

    def _show_session_end_dialog(self, hr, cr, dp):
        animal_id  = self.exp.animal_id
        log_file   = self.exp._log_file
        idx        = self._animal_index
        total      = len(self._animal_queue)
        has_next   = idx + 1 < total

        dlg = tk.Toplevel(self)
        dlg.title("Deney Tamamlandı")
        dlg.resizable(False, False)
        dlg.grab_set()

        msg = (
            f"Hayvan: {animal_id}  ({idx + 1}/{total})\n"
            f"Toplam: {config.NUM_TRIALS} trial\n\n"
            f"Hit Rate (DS+):      {hr:.1%}\n"
            f"Correct Rej (DS−):   {cr:.1%}\n"
            f"d' (diskriminasyon): {dp:.2f}\n\n"
            f"Log: {os.path.basename(log_file) if log_file else '—'}"
        )
        ttk.Label(dlg, text=msg, justify="left", padding=16).pack()

        btn_frame = ttk.Frame(dlg); btn_frame.pack(pady=8)

        if has_next:
            next_id = self._animal_queue[idx + 1]
            def _next():
                dlg.destroy()
                self._animal_index += 1
                self._start_next_animal()
            ttk.Button(btn_frame, text=f"Sonraki Hayvan: {next_id}  →",
                       command=_next).pack(side="left", padx=8)

        def _finish():
            dlg.destroy()
            self.btn_start.configure(state="normal")
            self.lbl_animal_queue.config(text="Tüm hayvanlar tamamlandı." if not has_next else "")
            if not has_next:
                logging.getLogger("App").info("Tüm hayvanlar tamamlandı.")
        ttk.Button(btn_frame, text="Bitir", command=_finish).pack(side="left", padx=8)

    def _on_trial_end(self, trial_num, ds, result, rt_ds, rt_lever):
        def _update():
            if not self.exp:
                return
            s = self.exp.stats
            self.lbl_reward._var.set(str(s["rewarded"]))
            self.lbl_punish._var.set(str(s["punished"]))
            self.lbl_omit._var.set(str(s["omission"]))
            self.lbl_cr._var.set(str(s["correct_rejection"]))
            self.lbl_lick_trial._var.set("0")
            if self.exp._log_file:
                self.lbl_logf._var.set(os.path.basename(self.exp._log_file))
        self.after(0, _update)

    def _on_lick_update(self, trial_licks: int, total_licks: int):
        def _update():
            self.lbl_lick_trial._var.set(str(trial_licks))
            self.lbl_lick_total._var.set(str(total_licks))
        self.after(0, _update)

    def _on_disc_update(self, hit_rate: float, cr_rate: float, d_prime: float):
        def _update():
            self.lbl_hit_rate._var.set(f"{hit_rate:.1%}")
            self.lbl_cr_rate._var.set(f"{cr_rate:.1%}")
            self.lbl_dprime._var.set(f"{d_prime:.2f}")
            self.dprime_bar["value"] = min(4.0, max(0.0, d_prime))
        self.after(0, _update)

    def _on_iti_press(self, trial_presses: int, total_presses: int):
        def _update():
            self.lbl_iti_trial._var.set(str(trial_presses))
            self.lbl_iti_total._var.set(str(total_presses))
        self.after(0, _update)

    # ── Donanım Testi ─────────────────────────────────────────────────────────

    def _hw_lever_extend(self):
        side = 0x01 if "Sol" in self.var_lever_side.get() else 0x02
        self.box.lever_extend(side)
        logging.getLogger("HW").info("Lever çıkarıldı")

    def _hw_lever_retract(self):
        side = 0x01 if "Sol" in self.var_lever_side.get() else 0x02
        self.box.lever_retract(side)
        logging.getLogger("HW").info("Lever geri alındı")

    def _hw_water(self):
        pulses = int(self.var_water_pulses.get())
        gap_ms = int(config.WATER_PULSE_GAP_S * 1000)
        log = logging.getLogger("HW")
        log.info(f"Su: {pulses} pulse")
        def _send_pulse(remaining):
            if remaining <= 0:
                return
            self.box.water(config.WATER_SIDE)
            self.after(gap_ms, lambda: _send_pulse(remaining - 1))
        _send_pulse(pulses)

    def _hw_shock(self):
        dur = self._hw_shock_dur.get()
        ma = float(self.var_shock_ma.get())
        self.box.shock_current(ma)
        self.box.shock(True)
        logging.getLogger("HW").info(f"Şok: {dur} sn / {ma} mA")
        self.after(int(dur * 1000), lambda: self.box.shock(False))

    def _hw_house_on(self):
        r, g, b = config.HOUSE_LIGHT_COLOR
        self.box.house_light(r, g, b)
        logging.getLogger("HW").info("House light yakıldı")

    def _hw_house_off(self):
        self.box.house_light_off()
        logging.getLogger("HW").info("House light söndürüldü")

    def _hw_bnc(self):
        voltage = float(self.var_ttl_voltage.get())
        duration = int(self.var_ttl_plus_dur.get())
        self.box.bnc_ttl(voltage, duration)
        logging.getLogger("HW").info(
            f"BNC TTL gönderildi: {voltage}V / {duration}ms")

    def _hw_avisoft_trigger(self):
        if self.exp and self.exp.avisoft_trigger:
            ok = self.exp.avisoft_trigger.trigger()
            if not ok:
                logging.getLogger("HW").error(
                    "Avisoft trigger başarısız — 'Pencere Listesi' butonuna basarak "
                    "doğru pencere adını log'dan kontrol edin.")
        else:
            logging.getLogger("HW").warning(
                "Avisoft trigger yüklü değil (pywin32 eksik veya bağlantı kurulmamış)")

    def _hw_avisoft_list_windows(self):
        t = self.exp.avisoft_trigger if self.exp else None
        if t is None:
            try:
                from avisoft_trigger import AvisoftTrigger
                t = AvisoftTrigger()
            except Exception as e:
                logging.getLogger("HW").error(f"AvisoftTrigger yüklenemedi: {e}")
                return
        t.list_windows()
        t.list_children()

    # ── Rapor ─────────────────────────────────────────────────────────────────

    def _generate_report(self):
        import report as rpt
        csv_path = filedialog.askopenfilename(
            title="CSV Dosyası Seç",
            initialdir=config.LOG_DIR,
            filetypes=[("CSV", "*.csv"), ("Tüm dosyalar", "*.*")]
        )
        if not csv_path:
            return
        try:
            html_path, xlsx_path = rpt.generate_report(csv_path)
            webbrowser.open(f"file://{os.path.abspath(html_path)}")
            logging.getLogger("App").info(f"HTML:  {html_path}")
            logging.getLogger("App").info(f"Excel: {xlsx_path}")
        except Exception as e:
            messagebox.showerror("Hata", str(e))

    # ── Kapat ─────────────────────────────────────────────────────────────────

    def _on_close(self):
        if self.exp:
            self.exp.stop()
        if self.box:
            self.box.disconnect()
        self.destroy()


# ── Giriş noktası ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = App()
    app.mainloop()
