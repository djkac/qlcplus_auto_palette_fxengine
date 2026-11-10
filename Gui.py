#!/usr/bin/env python3
"""
QLC+ Auto Palette FX Engine — Guided Wizard GUI
A beginner-friendly, visual wizard for Windows, macOS, and Linux
to automatically generate complete QLC+ palettes, scenes, movements, and chasers.
"""

import os
import sys
import queue
import threading
import subprocess
import platform
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import xml.etree.ElementTree as ET

import qlcplus_auto_palette_fxengine as engine


def inspect_workspace(filepath):
    """
    Parses a .qxw file and returns a summary dict of its fixtures and contents.
    """
    if not filepath or not os.path.isfile(filepath):
        return None
    try:
        root = engine.strip_ns(engine.safe_xml_parse(filepath))
        fixtures = engine.parse_qxw_fixtures(root)
        groups = engine.parse_qxw_fixture_groups(root)
        eng_elem = root.find("Engine")
        functions_count = len(eng_elem.findall("Function")) if eng_elem is not None else 0
        return {
            "fixtures": fixtures,
            "groups": groups,
            "functions_count": functions_count,
            "creator": (root.find("Creator/Name").text if root.find("Creator/Name") is not None else "QLC+"),
            "version": (root.find("Creator/Version").text if root.find("Creator/Version") is not None else "4.x"),
        }
    except Exception as e:
        return {"error": str(e), "fixtures": [], "groups": [], "functions_count": 0}


class QLCPaletteWizard(tk.Tk):
    def __init__(self, initial_file=None):
        super().__init__()
        self.title("QLC+ Auto Palette FX Engine — Wizard")
        self.geometry("860x660")
        self.minsize(780, 580)

        # Apply a clean modern theme
        self._setup_style()

        # State variables
        self.input_path_var = tk.StringVar(value=initial_file or "")
        self.output_path_var = tk.StringVar(value="")
        self.fixture_dir_var = tk.StringVar(value="")
        self.profile_var = tk.StringVar(value="max")  # 'max', 'compact', 'custom'
        self.lang_var = tk.StringVar(value="en")  # 'en' or 'it'
        self.fade_in_var = tk.IntVar(value=0)
        self.fade_out_var = tk.IntVar(value=2000)
        self.overwrite_var = tk.BooleanVar(value=True)

        # Custom options (used if profile == 'custom' or preset applied)
        self.opt_efx_var = tk.BooleanVar(value=True)
        self.opt_chasers_var = tk.BooleanVar(value=True)
        self.opt_groups_var = tk.BooleanVar(value=True)
        self.opt_combos_var = tk.BooleanVar(value=True)

        # Generation result store
        self.generation_result = None
        self.is_generating = False
        self.msg_queue = queue.Queue()

        # Wizard step index (0: Project, 1: Preset & Options, 2: Generate & Results)
        self.current_step = 0

        # UI Layout
        self._build_header()
        self._build_container()
        self._build_footer()

        # Build individual step frames
        self.frames = [
            self._create_step1_frame(self.container),
            self._create_step2_frame(self.container),
            self._create_step3_frame(self.container),
        ]

        if initial_file:
            self._on_input_file_selected(initial_file)

        self._show_step(0)
        self._poll_queue()

    def _poll_queue(self):
        """Processes messages dispatched from background worker threads safely on the main thread."""
        try:
            while True:
                msg_type, payload = self.msg_queue.get_nowait()
                if msg_type == "log":
                    self.log_text.insert(tk.END, payload + "\n")
                    self.log_text.see(tk.END)
                elif msg_type == "finished":
                    result, error = payload
                    self._on_generation_finished(result, error)
        except queue.Empty:
            pass
        self.after(50, self._poll_queue)

    def _setup_style(self):
        self.style = ttk.Style(self)
        try:
            self.style.theme_use("clam")
        except Exception:
            pass

        # Color palette
        bg_dark = "#1e293b"
        text_dark = "#0f172a"
        text_muted = "#64748b"

        self.configure(bg="#f1f5f9")

        self.style.configure(".", font=("Segoe UI", 10))
        self.style.configure("Header.TFrame", background=bg_dark)
        self.style.configure("HeaderTitle.TLabel", background=bg_dark, foreground="#ffffff", font=("Segoe UI", 16, "bold"))
        self.style.configure("HeaderSub.TLabel", background=bg_dark, foreground="#94a3b8", font=("Segoe UI", 10))

        self.style.configure("StepIndicator.TLabel", background=bg_dark, foreground="#38bdf8", font=("Segoe UI", 11, "bold"))

        self.style.configure("Card.TFrame", background="#ffffff", relief="flat")
        self.style.configure("CardHeader.TLabel", background="#ffffff", foreground=text_dark, font=("Segoe UI", 12, "bold"))
        self.style.configure("CardMuted.TLabel", background="#ffffff", foreground=text_muted, font=("Segoe UI", 9))

        self.style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), padding=(16, 8))
        self.style.configure("Secondary.TButton", font=("Segoe UI", 10), padding=(12, 8))
        self.style.configure("BigAction.TButton", font=("Segoe UI", 12, "bold"), padding=(20, 10))

    def _build_header(self):
        header = ttk.Frame(self, style="Header.TFrame", padding=(20, 16))
        header.pack(fill="x", side="top")

        left = ttk.Frame(header, style="Header.TFrame")
        left.pack(side="left", fill="both", expand=True)

        title = ttk.Label(left, text="✨ QLC+ Auto Palette FX Engine", style="HeaderTitle.TLabel")
        title.pack(anchor="w")

        subtitle = ttk.Label(left, text="Instant DJ scenes, movement effects, and chaser generator", style="HeaderSub.TLabel")
        subtitle.pack(anchor="w", pady=(2, 0))

        self.step_label = ttk.Label(header, text="Step 1 of 3", style="StepIndicator.TLabel")
        self.step_label.pack(side="right", padx=(10, 0))

    def _build_container(self):
        self.container = ttk.Frame(self, padding=(20, 16))
        self.container.pack(fill="both", expand=True)

    def _build_footer(self):
        footer_outer = ttk.Frame(self, padding=(20, 12))
        footer_outer.pack(fill="x", side="bottom")

        sep = ttk.Separator(self, orient="horizontal")
        sep.pack(fill="x", side="bottom")

        self.btn_back = ttk.Button(footer_outer, text="← Back", style="Secondary.TButton", command=self._go_back)
        self.btn_back.pack(side="left")

        self.btn_next = ttk.Button(footer_outer, text="Next Step →", style="Primary.TButton", command=self._go_next)
        self.btn_next.pack(side="right")

    def _create_step1_frame(self, parent):
        frame = ttk.Frame(parent)

        card = ttk.LabelFrame(frame, text=" 1. Select your QLC+ Show File (.qxw) ", padding=(16, 14))
        card.pack(fill="x", pady=(0, 14))

        desc = ttk.Label(
            card,
            text="Choose your existing QLC+ project. The tool will read your patched lighting fixtures and build an entire palette for you.\nYour original file is NEVER overwritten — a brand new palette file will be created safely.",
            wraplength=760,
            justify="left",
        )
        desc.pack(anchor="w", pady=(0, 12))

        row_in = ttk.Frame(card)
        row_in.pack(fill="x", pady=(0, 8))
        ttk.Label(row_in, text="Input File:", width=12).pack(side="left")
        entry_in = ttk.Entry(row_in, textvariable=self.input_path_var, font=("Segoe UI", 10))
        entry_in.pack(side="left", fill="x", expand=True, padx=(4, 8))
        btn_browse_in = ttk.Button(row_in, text="Browse...", command=self._browse_input_file)
        btn_browse_in.pack(side="right")

        row_out = ttk.Frame(card)
        row_out.pack(fill="x", pady=(0, 4))
        ttk.Label(row_out, text="Save Palette As:", width=12).pack(side="left")
        entry_out = ttk.Entry(row_out, textvariable=self.output_path_var, font=("Segoe UI", 10))
        entry_out.pack(side="left", fill="x", expand=True, padx=(4, 8))
        btn_browse_out = ttk.Button(row_out, text="Change...", command=self._browse_output_file)
        btn_browse_out.pack(side="right")

        fixtures_card = ttk.LabelFrame(frame, text=" Detected Lights & Hardware Fixtures ", padding=(14, 12))
        fixtures_card.pack(fill="both", expand=True)

        self.fixture_summary_label = ttk.Label(fixtures_card, text="No project selected yet. Click 'Browse...' above.", font=("Segoe UI", 10, "italic"))
        self.fixture_summary_label.pack(anchor="w", pady=(0, 8))

        cols = ("id", "name", "model", "mode", "address")
        self.fixture_tree = ttk.Treeview(fixtures_card, columns=cols, show="headings", height=8)
        self.fixture_tree.heading("id", text="ID")
        self.fixture_tree.heading("name", text="Fixture Name")
        self.fixture_tree.heading("model", text="Manufacturer & Model")
        self.fixture_tree.heading("mode", text="Mode")
        self.fixture_tree.heading("address", text="DMX Universe / Address")

        self.fixture_tree.column("id", width=50, anchor="center")
        self.fixture_tree.column("name", width=200)
        self.fixture_tree.column("model", width=220)
        self.fixture_tree.column("mode", width=120)
        self.fixture_tree.column("address", width=130, anchor="center")

        tree_scroll = ttk.Scrollbar(fixtures_card, orient="vertical", command=self.fixture_tree.yview)
        self.fixture_tree.configure(yscrollcommand=tree_scroll.set)

        self.fixture_tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")

        return frame

    def _create_step2_frame(self, parent):
        frame = ttk.Frame(parent)

        preset_card = ttk.LabelFrame(frame, text=" 2. Choose Your Generation Style ", padding=(16, 14))
        preset_card.pack(fill="x", pady=(0, 14))

        r1_box = ttk.Frame(preset_card, padding=(4, 6))
        r1_box.pack(fill="x", anchor="w")
        r1 = ttk.Radiobutton(
            r1_box,
            text="🌟 Maximum Show (Best for Parties & DJing — Recommended)",
            value="max",
            variable=self.profile_var,
            command=self._on_preset_changed,
        )
        r1.pack(anchor="w")
        r1_desc = ttk.Label(
            r1_box,
            text="   Generates all individual & group effects: 35+ colors, 29 pan/tilt positions, 19 movement EFX\n   (circle, 8, lissajous, diamond) and all chaser sequences (rainbow, police, stomp, heartbeat, sweeps).",
            foreground="#475569",
        )
        r1_desc.pack(anchor="w", padx=(24, 0))

        r2_box = ttk.Frame(preset_card, padding=(4, 6))
        r2_box.pack(fill="x", anchor="w")
        r2 = ttk.Radiobutton(
            r2_box,
            text="⚡ Compact Palette (Clean & Essential)",
            value="compact",
            variable=self.profile_var,
            command=self._on_preset_changed,
        )
        r2.pack(anchor="w")
        r2_desc = ttk.Label(
            r2_box,
            text="   Generates full scenes and group functions, but omits single-fixture duplicates when fixtures\n   are already part of a group. Perfect for keeping function lists short.",
            foreground="#475569",
        )
        r2_desc.pack(anchor="w", padx=(24, 0))

        r3_box = ttk.Frame(preset_card, padding=(4, 6))
        r3_box.pack(fill="x", anchor="w")
        r3 = ttk.Radiobutton(
            r3_box,
            text="🛠️ Custom / Advanced Settings",
            value="custom",
            variable=self.profile_var,
            command=self._on_preset_changed,
        )
        r3.pack(anchor="w")

        self.options_card = ttk.LabelFrame(frame, text=" Options & Timings ", padding=(16, 12))
        self.options_card.pack(fill="both", expand=True)

        col1 = ttk.Frame(self.options_card)
        col1.pack(side="left", fill="both", expand=True, padx=(0, 20))

        ttk.Label(col1, text="Features to Include:", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 6))
        self.cb_efx = ttk.Checkbutton(col1, text="Movement EFX (Circle, Line, Figure-8, Leaves...)", variable=self.opt_efx_var)
        self.cb_efx.pack(anchor="w", pady=2)
        self.cb_chasers = ttk.Checkbutton(col1, text="Chaser Sequences (Rainbow, Stomp, Flash, Sweeps...)", variable=self.opt_chasers_var)
        self.cb_chasers.pack(anchor="w", pady=2)
        self.cb_groups = ttk.Checkbutton(col1, text="Group Synchronized Effects & Chasers", variable=self.opt_groups_var)
        self.cb_groups.pack(anchor="w", pady=2)
        self.cb_combos = ttk.Checkbutton(col1, text="Quick Combos (Stage Ready, Blackout, Full Show)", variable=self.opt_combos_var)
        self.cb_combos.pack(anchor="w", pady=2)

        col2 = ttk.Frame(self.options_card)
        col2.pack(side="right", fill="both", expand=True)

        ttk.Label(col2, text="Language & Timings:", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 6))

        row_lang = ttk.Frame(col2)
        row_lang.pack(fill="x", pady=2)
        ttk.Label(row_lang, text="Language:", width=14).pack(side="left")
        ttk.Radiobutton(row_lang, text="English", value="en", variable=self.lang_var).pack(side="left", padx=(0, 10))
        ttk.Radiobutton(row_lang, text="Italiano", value="it", variable=self.lang_var).pack(side="left")

        row_fade = ttk.Frame(col2)
        row_fade.pack(fill="x", pady=4)
        ttk.Label(row_fade, text="Scene Fade Out:", width=14).pack(side="left")
        fade_combo = ttk.Combobox(row_fade, textvariable=self.fade_out_var, values=[0, 500, 1000, 2000, 3000, 5000], width=8)
        fade_combo.pack(side="left", padx=(0, 4))
        ttk.Label(row_fade, text="ms").pack(side="left")

        row_fdir = ttk.Frame(col2)
        row_fdir.pack(fill="x", pady=(8, 2))
        ttk.Label(row_fdir, text="Custom .qxf dir (optional):").pack(anchor="w")
        row_fdir_in = ttk.Frame(row_fdir)
        row_fdir_in.pack(fill="x", pady=(2, 0))
        ttk.Entry(row_fdir_in, textvariable=self.fixture_dir_var).pack(side="left", fill="x", expand=True, padx=(0, 4))
        ttk.Button(row_fdir_in, text="Browse", width=7, command=self._browse_fixture_dir).pack(side="right")

        self._on_preset_changed()
        return frame

    def _create_step3_frame(self, parent):
        frame = ttk.Frame(parent)

        top_box = ttk.Frame(frame, padding=(0, 0, 0, 10))
        top_box.pack(fill="x")

        self.btn_run = ttk.Button(
            top_box,
            text="🚀 Generate Complete Light Palette Now!",
            style="BigAction.TButton",
            command=self._start_generation,
        )
        self.btn_run.pack(side="left")

        self.progress_bar = ttk.Progressbar(top_box, mode="indeterminate", length=220)

        self.summary_card = ttk.LabelFrame(frame, text=" Generation Results & Summary ", padding=(14, 12))
        self.summary_card.pack(fill="x", pady=(0, 10))

        self.stat_label = ttk.Label(
            self.summary_card,
            text="Click the button above to begin generating scenes, movements, and chasers.",
            font=("Segoe UI", 11, "bold"),
            foreground="#1e293b",
        )
        self.stat_label.pack(anchor="w", pady=(0, 6))

        self.actions_frame = ttk.Frame(self.summary_card)
        self.btn_open_folder = ttk.Button(self.actions_frame, text="📁 Open Output Folder", command=self._open_output_folder)
        self.btn_open_folder.pack(side="left", padx=(0, 8))
        self.btn_open_qlc = ttk.Button(self.actions_frame, text="💡 Launch in QLC+", command=self._open_in_qlcplus)
        self.btn_open_qlc.pack(side="left")

        log_card = ttk.LabelFrame(frame, text=" Live Activity Console ", padding=(10, 8))
        log_card.pack(fill="both", expand=True)

        self.log_text = tk.Text(log_card, wrap="word", font=("Consolas", 9), bg="#0f172a", fg="#f8fafc", relief="flat")
        log_scroll = ttk.Scrollbar(log_card, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)

        self.log_text.pack(side="left", fill="both", expand=True)
        log_scroll.pack(side="right", fill="y")

        return frame

    def _show_step(self, step_idx):
        for i, frame in enumerate(self.frames):
            if i == step_idx:
                frame.pack(fill="both", expand=True)
            else:
                frame.pack_forget()

        self.current_step = step_idx
        self.step_label.config(text=f"Step {step_idx + 1} of 3")

        self.btn_back.config(state="normal" if step_idx > 0 else "disabled")
        if step_idx == 0:
            self.btn_next.config(text="Next: Style & Options →", state="normal")
        elif step_idx == 1:
            self.btn_next.config(text="Next: Review & Generate →", state="normal")
        elif step_idx == 2:
            self.btn_next.config(text="Finished 🎉", state="disabled" if not self.generation_result else "normal")

    def _go_back(self):
        if self.current_step > 0:
            self._show_step(self.current_step - 1)

    def _go_next(self):
        if self.current_step == 0:
            in_path = self.input_path_var.get().strip()
            if not in_path or not os.path.isfile(in_path):
                messagebox.showerror("File Required", "Please select a valid QLC+ project file (.qxw) to continue.")
                return
            if not self.output_path_var.get().strip():
                self.output_path_var.set(in_path.replace(".qxw", "_palette.qxw"))
            self._show_step(1)
        elif self.current_step == 1:
            self._show_step(2)
        elif self.current_step == 2:
            self.destroy()

    def _browse_input_file(self):
        filename = filedialog.askopenfilename(
            title="Select QLC+ Project File",
            filetypes=[("QLC+ Workspace (*.qxw)", "*.qxw"), ("All Files (*.*)", "*.*")],
        )
        if filename:
            self.input_path_var.set(filename)
            self._on_input_file_selected(filename)

    def _browse_output_file(self):
        initial = self.output_path_var.get() or "my_show_palette.qxw"
        filename = filedialog.asksaveasfilename(
            title="Save Generated Workspace As",
            initialfile=os.path.basename(initial),
            filetypes=[("QLC+ Workspace (*.qxw)", "*.qxw"), ("All Files (*.*)", "*.*")],
        )
        if filename:
            if not filename.lower().endswith(".qxw"):
                filename += ".qxw"
            self.output_path_var.set(filename)

    def _browse_fixture_dir(self):
        folder = filedialog.askdirectory(title="Select Custom Fixtures (.qxf) Folder")
        if folder:
            self.fixture_dir_var.set(folder)

    def _on_input_file_selected(self, filepath):
        if not self.output_path_var.get().strip() or "_palette.qxw" in self.output_path_var.get():
            self.output_path_var.set(filepath.replace(".qxw", "_palette.qxw"))

        info = inspect_workspace(filepath)
        for item in self.fixture_tree.get_children():
            self.fixture_tree.delete(item)

        if not info or "error" in info:
            err = info.get("error", "Invalid file") if info else "File not found"
            self.fixture_summary_label.config(text=f"⚠️ Error reading workspace: {err}", foreground="#ef4444")
            return

        fixtures = info.get("fixtures", [])
        groups = info.get("groups", [])
        fn_count = info.get("functions_count", 0)

        summary_text = (
            f"✅ Found {len(fixtures)} patched fixture(s) and {len(groups)} group(s). "
            f"Existing functions in project: {fn_count}."
        )
        self.fixture_summary_label.config(text=summary_text, foreground="#15803d")

        for f in fixtures:
            addr_str = f"Univ {f['universe'] + 1} @ DMX {f['address'] + 1} ({f['channels']} ch)"
            self.fixture_tree.insert(
                "",
                "end",
                values=(f["id"], f["name"], f"{f['manufacturer']} {f['model']}", f["mode"], addr_str),
            )

    def _on_preset_changed(self):
        mode = self.profile_var.get()
        if mode == "max" or mode == "compact":
            self.opt_efx_var.set(True)
            self.opt_chasers_var.set(True)
            self.opt_groups_var.set(True)
            self.opt_combos_var.set(True)
            self._set_advanced_state("disabled")
        else:  # custom
            self._set_advanced_state("normal")

    def _set_advanced_state(self, state):
        self.cb_efx.config(state=state)
        self.cb_chasers.config(state=state)
        self.cb_groups.config(state=state)
        self.cb_combos.config(state=state)

    def _start_generation(self):
        if self.is_generating:
            return

        in_file = self.input_path_var.get().strip()
        out_file = self.output_path_var.get().strip()

        if not in_file or not os.path.isfile(in_file):
            messagebox.showerror("Error", "Please select a valid input QLC+ workspace (.qxw) file.")
            return

        self.is_generating = True
        self.btn_run.config(state="disabled")
        self.btn_back.config(state="disabled")
        self.progress_bar.pack(side="right", padx=(10, 0))
        self.progress_bar.start(10)

        self.log_text.delete("1.0", tk.END)
        self.actions_frame.pack_forget()
        self.stat_label.config(text="Generating palette... Please wait...", foreground="#2563eb")

        profile_mode = "completo" if self.profile_var.get() == "max" else "compatto"
        skip_efx = not self.opt_efx_var.get()
        skip_chasers = not self.opt_chasers_var.get()
        skip_groups = not self.opt_groups_var.get()
        skip_combos = not self.opt_combos_var.get()
        fade_out = int(self.fade_out_var.get() or 2000)
        fade_in = int(self.fade_in_var.get() or 0)
        fixture_dir = self.fixture_dir_var.get().strip() or None
        lang = self.lang_var.get()

        def run_thread():
            error_occurred = None
            result = None
            try:
                result = engine.generate_palette(
                    input_path=in_file,
                    output_path=out_file,
                    fixture_dir=fixture_dir,
                    fade_in=fade_in,
                    fade_out=fade_out,
                    overwrite=self.overwrite_var.get(),
                    skip_groups=skip_groups,
                    skip_combos=skip_combos,
                    skip_efx=skip_efx,
                    skip_chasers=skip_chasers,
                    profile=profile_mode,
                    lang=lang,
                    log_callback=lambda txt: self.msg_queue.put(("log", txt)),
                )
            except Exception as e:
                error_occurred = e

            self.msg_queue.put(("finished", (result, error_occurred)))

        threading.Thread(target=run_thread, daemon=True).start()

    def _on_generation_finished(self, result, error):
        self.is_generating = False
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        self.btn_run.config(state="normal")
        self.btn_back.config(state="normal")

        if error:
            self.stat_label.config(text=f"❌ Error during generation: {error}", foreground="#dc2626")
            messagebox.showerror("Generation Error", f"An error occurred while generating palette:\n\n{error}")
            return

        self.generation_result = result
        scenes = result["added_scenes"]
        efx = result["added_efx"]
        chasers = result["added_chasers"]
        total = scenes + efx + chasers

        msg = (
            f"🎉 Success! Generated {total:,} lighting functions ({scenes} scenes, {efx} EFX movements, "
            f"{chasers} chaser sequences) for {result['fixtures_count']} fixtures!"
        )
        self.stat_label.config(text=msg, foreground="#15803d")
        self.actions_frame.pack(anchor="w", pady=(8, 0))
        self.btn_next.config(state="normal", text="Finished 🎉")

    def _open_output_folder(self):
        out_path = self.output_path_var.get()
        if not out_path:
            return
        folder = os.path.dirname(os.path.abspath(out_path))
        if platform.system() == "Windows":
            os.startfile(folder)
        elif platform.system() == "Darwin":
            subprocess.run(["open", folder], check=False)
        else:
            subprocess.run(["xdg-open", folder], check=False)

    def _open_in_qlcplus(self):
        out_path = self.output_path_var.get()
        if not out_path or not os.path.isfile(out_path):
            messagebox.showwarning("File not found", "Generated file not found on disk.")
            return

        abs_file = os.path.abspath(out_path)
        system = platform.system()
        try:
            if system == "Windows":
                try:
                    os.startfile(abs_file)
                    return
                except Exception:
                    qlc_paths = [
                        r"C:\QLC+\qlcplus.exe",
                        r"C:\Program Files\QLC+\qlcplus.exe",
                        r"C:\Program Files (x86)\QLC+\qlcplus.exe",
                    ]
                    for p in qlc_paths:
                        if os.path.isfile(p):
                            subprocess.Popen([p, abs_file])
                            return
            elif system == "Darwin":
                subprocess.Popen(["open", "-a", "QLC+", abs_file])
                return
            else:
                subprocess.Popen(["qlcplus", abs_file])
                return
        except Exception as e:
            messagebox.showinfo("Open in QLC+", f"Could not launch QLC+ automatically ({e}).\nYou can open {abs_file} directly in QLC+.")


def launch_gui(initial_file=None):
    """Entrypoint function to launch the Tkinter GUI."""
    app = QLCPaletteWizard(initial_file=initial_file)
    app.mainloop()


if __name__ == "__main__":
    init_file = sys.argv[1] if len(sys.argv) > 1 else None
    launch_gui(init_file)
