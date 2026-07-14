import os
import sys
import time
import threading
import subprocess
from tkinter import filedialog
import tkinter as tk
import customtkinter as ctk

# auto install dependencies if someone runs this clean python stuff gets installed in the bg causes false positives on virus scanners
try:
    from yt_dlp import YoutubeDL
    import imageio_ffmpeg
except ImportError:
    no_window_flag = 0x08000000 if os.name == 'nt' else 0
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "yt-dlp", "imageio-ffmpeg", "customtkinter"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=no_window_flag, check=True
        )
        from yt_dlp import YoutubeDL
        import imageio_ffmpeg
    except Exception:
        sys.exit(1)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ---------------------------------------------------------------------------
# Design tokens
# A broadcast-control-room identity: graphite surfaces, a signal-tally accent,
# and monospace timecodes so the IN/OUT fields read like a real NLE.
# ---------------------------------------------------------------------------
COLOR = {
    "bg":            "#0B1220",
    "surface":       "#131C2E",
    "surface_alt":   "#1B263B",
    "border":        "#2B3C5A",
    "border_soft":   "#23314A",

    # Baby Blue Theme
    "accent":        "#7DD3FC",   # Baby blue
    "accent_hover":  "#38BDF8",   # Slightly darker
    "accent_dim":    "#17384D",   # Dark blue background for badges

    "mint":          "#7DD3FC",   # Use blue instead of green
    "amber":         "#60A5FA",   # Blue for working state
    "danger":        "#EF4444",

    "text":          "#F8FAFC",
    "text_muted":    "#CBD5E1",
    "text_faint":    "#94A3B8",
}

FONT_DISPLAY = "Segoe UI"
FONT_MONO = "Consolas"  # tkinter silently falls back if unavailable on the host OS


def label_font(size=11, weight="bold"):
    return ctk.CTkFont(family=FONT_DISPLAY, size=size, weight=weight)


def mono_font(size=20, weight="bold"):
    return ctk.CTkFont(family=FONT_MONO, size=size, weight=weight)


class StatusDot(ctk.CTkCanvas):
    """Small tally-light style status indicator."""
    def __init__(self, master, size=10, **kwargs):
        super().__init__(master, width=size, height=size, bg=COLOR["surface"],
                          highlightthickness=0, **kwargs)
        self.size = size
        self._id = self.create_oval(1, 1, size - 1, size - 1, fill=COLOR["text_faint"], outline="")

    def set_color(self, hex_color):
        self.itemconfig(self._id, fill=hex_color)


class StreamClipApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("StreamClip Studio")

        # Auto maximize on startup
        self.configure(fg_color=COLOR["bg"])

        if os.name == "nt":
            self.state("zoomed")
        else:
            self.attributes("-zoomed", True)

        self.minsize(560, 780)
        self.resizable(True, True)

        # Setup desktop destination folder path
        home_dir = os.path.expanduser("~")
        self.desktop_folder = os.path.normpath(os.path.join(home_dir, "Desktop"))
        self.clips_folder = os.path.join(self.desktop_folder, "clips")

        if not os.path.exists(self.clips_folder):
            try:
                os.makedirs(self.clips_folder)
            except Exception:
                self.clips_folder = self.desktop_folder  # folder creation failed, default back to desktop

        # ---- Outer scaffold ------------------------------------------------
        self.shell = ctk.CTkFrame(self, corner_radius=0, fg_color=COLOR["bg"])
        self.shell.pack(fill="both", expand=True)

        self._build_header()

        self.body = ctk.CTkScrollableFrame(
            self.shell, fg_color="transparent",
            scrollbar_button_color=COLOR["border"],
            scrollbar_button_hover_color=COLOR["accent_dim"],
        )
        self.body.pack(fill="both", expand=True, padx=22, pady=(6, 0))

        self._build_source_card()
        self._build_output_card()
        self._build_timecode_card()
        self._build_settings_card()

        self._build_status_bar()
        self._build_action_bar()

    # ------------------------------------------------------------------ UI --

    def _card(self, title, subtitle=None, icon="—"):
        """A consistent bordered card with an eyebrow header."""
        wrap = ctk.CTkFrame(self.body, corner_radius=14, fg_color=COLOR["surface"],
                             border_width=1, border_color=COLOR["border"])
        wrap.pack(fill="x", pady=(0, 14))

        head = ctk.CTkFrame(wrap, fg_color="transparent")
        head.pack(fill="x", padx=20, pady=(16, 4))

        badge = ctk.CTkLabel(
            head, text=icon, width=22, height=22, corner_radius=6,
            fg_color=COLOR["accent_dim"], text_color=COLOR["accent"],
            font=label_font(12, "bold"),
        )
        badge.pack(side="left", padx=(0, 10))

        title_box = ctk.CTkFrame(head, fg_color="transparent")
        title_box.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(title_box, text=title, font=label_font(12, "bold"),
                     text_color=COLOR["text"], anchor="w").pack(anchor="w")
        if subtitle:
            ctk.CTkLabel(title_box, text=subtitle, font=label_font(10, "normal"),
                         text_color=COLOR["text_faint"], anchor="w").pack(anchor="w")

        content = ctk.CTkFrame(wrap, fg_color="transparent")
        content.pack(fill="x", padx=20, pady=(6, 18))
        return content

    def _field(self, parent, label_text):
        ctk.CTkLabel(parent, text=label_text, font=label_font(10, "bold"),
                     text_color=COLOR["text_muted"]).pack(anchor="w", pady=(0, 6))

    def _entry(self, parent, **kwargs):
        return ctk.CTkEntry(
            parent, height=40, corner_radius=9,
            fg_color=COLOR["surface_alt"], border_width=1,
            border_color=COLOR["border"], text_color=COLOR["text"],
            placeholder_text_color=COLOR["text_faint"],
            font=label_font(12, "normal"),
            **kwargs,
        )

    def _build_header(self):
        header = ctk.CTkFrame(self.shell, fg_color=COLOR["surface"], corner_radius=0,
                               border_width=0, height=88)
        header.pack(fill="x")
        header.pack_propagate(False)

        inner = ctk.CTkFrame(header, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=22, pady=14)

        # logo mark
        logo = ctk.CTkLabel(
            inner, text="SC", width=44, height=44, corner_radius=10,
            fg_color=COLOR["accent"], text_color="#0B0C0E",
            font=ctk.CTkFont(family=FONT_DISPLAY, size=15, weight="bold"),
        )
        logo.pack(side="left")

        title_box = ctk.CTkFrame(inner, fg_color="transparent")
        title_box.pack(side="left", fill="y", padx=(14, 0))
        ctk.CTkLabel(title_box, text="STREAMCLIP STUDIO", font=label_font(17, "bold"),
                     text_color=COLOR["text"], anchor="w").pack(anchor="w")
        ctk.CTkLabel(title_box, text="Capture & Clip Suite  •  v2.0", font=label_font(10, "normal"),
                     text_color=COLOR["text_faint"], anchor="w").pack(anchor="w")

        # live status pill top-right
        pill = ctk.CTkFrame(inner, fg_color=COLOR["surface_alt"], corner_radius=20,
                             border_width=1, border_color=COLOR["border"])
        pill.pack(side="right")
        pill_inner = ctk.CTkFrame(pill, fg_color="transparent")
        pill_inner.pack(padx=12, pady=6)
        self.header_dot = StatusDot(pill_inner, size=9)
        self.header_dot.configure(bg=COLOR["surface_alt"])
        self.header_dot.pack(side="left", padx=(0, 7))
        self.header_dot.set_color(COLOR["mint"])
        self.lbl_ready = ctk.CTkLabel(pill_inner, text="READY", font=label_font(10, "bold"),
                                       text_color=COLOR["text_muted"])
        self.lbl_ready.pack(side="left")

    def _build_source_card(self):
        c = self._card("SOURCE", "Paste a video or livestream URL", icon="🔗")
        self._field(c, "TARGET VIDEO OR STREAM URL")
        self.ent_url = self._entry(c, placeholder_text="https://...")
        self.ent_url.pack(fill="x")

    def _build_output_card(self):
        c = self._card("OUTPUT", "Where the finished file gets saved", icon="📁")

        self._field(c, "CUSTOM FILENAME  (OPTIONAL)")
        self.ent_file = self._entry(c, placeholder_text="Defaults to a timestamped name")
        self.ent_file.pack(fill="x", pady=(0, 14))

        self._field(c, "SAVE LOCATION")
        row = ctk.CTkFrame(c, fg_color="transparent")
        row.pack(fill="x")
        self.ent_loc = self._entry(row)
        self.ent_loc.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.ent_loc.insert(0, self.clips_folder)

        self.btn_browse = ctk.CTkButton(
            row, text="Browse", width=88, height=40, corner_radius=9,
            fg_color=COLOR["surface_alt"], hover_color=COLOR["border"],
            border_width=1, border_color=COLOR["border"],
            text_color=COLOR["text"], font=label_font(11, "bold"),
            command=self.find_local_folder,
        )
        self.btn_browse.pack(side="right")

    def _build_timecode_card(self):
        c = self._card("TIMECODE", "Trim range for clip mode (ignored for full capture)", icon="⏱")

        row = ctk.CTkFrame(c, fg_color="transparent")
        row.pack(fill="x")

        in_box = ctk.CTkFrame(row, fg_color=COLOR["surface_alt"], corner_radius=10,
                               border_width=1, border_color=COLOR["border"])
        in_box.pack(side="left", expand=True, fill="both", padx=(0, 8))
        ctk.CTkLabel(in_box, text="IN", font=label_font(9, "bold"),
                     text_color=COLOR["accent"]).pack(anchor="w", padx=14, pady=(10, 0))
        self.ent_start = ctk.CTkEntry(in_box, fg_color="transparent", border_width=0,
                                       font=mono_font(20), text_color=COLOR["text"],
                                       justify="center")
        self.ent_start.pack(fill="x", padx=10, pady=(0, 12))
        self.ent_start.insert(0, "00:01:00")

        sep = ctk.CTkLabel(row, text="→", font=label_font(16, "bold"), text_color=COLOR["text_faint"], width=24)
        sep.pack(side="left")

        out_box = ctk.CTkFrame(row, fg_color=COLOR["surface_alt"], corner_radius=10,
                                border_width=1, border_color=COLOR["border"])
        out_box.pack(side="right", expand=True, fill="both", padx=(8, 0))
        ctk.CTkLabel(out_box, text="OUT", font=label_font(9, "bold"),
                     text_color=COLOR["accent"]).pack(anchor="w", padx=14, pady=(10, 0))
        self.ent_end = ctk.CTkEntry(out_box, fg_color="transparent", border_width=0,
                                     font=mono_font(20), text_color=COLOR["text"],
                                     justify="center")
        self.ent_end.pack(fill="x", padx=10, pady=(0, 12))
        self.ent_end.insert(0, "00:01:30")

        ctk.CTkLabel(c, text="Format  HH:MM:SS", font=label_font(9, "normal"),
                     text_color=COLOR["text_faint"]).pack(anchor="w", pady=(8, 0))

    def _build_settings_card(self):
        c = self._card("CAPTURE SETTINGS", "Quality ceiling for the downloaded stream", icon="🎚")

        row = ctk.CTkFrame(c, fg_color="transparent")
        row.pack(fill="x")

        res_box = ctk.CTkFrame(row, fg_color="transparent")
        res_box.pack(side="left", expand=True, fill="x", padx=(0, 10))
        self._field(res_box, "MAX RESOLUTION")
        self.drop_res = ctk.CTkOptionMenu(
            res_box, values=["4K (2160p)", "2K (1440p)", "1080p", "720p", "480p", "360p"],
            height=40, corner_radius=9, fg_color=COLOR["surface_alt"],
            button_color=COLOR["border"], button_hover_color=COLOR["accent_dim"],
            text_color=COLOR["text"], font=label_font(12, "normal"),
            dropdown_fg_color=COLOR["surface_alt"], dropdown_hover_color=COLOR["accent_dim"],
            dropdown_text_color=COLOR["text"],
        )
        self.drop_res.pack(fill="x")
        self.drop_res.set("1080p")

        fps_box = ctk.CTkFrame(row, fg_color="transparent")
        fps_box.pack(side="right", expand=True, fill="x", padx=(10, 0))
        self._field(fps_box, "MAX FRAMERATE")
        self.drop_fps = ctk.CTkOptionMenu(
            fps_box, values=["120 FPS", "60 FPS", "30 FPS"],
            height=40, corner_radius=9, fg_color=COLOR["surface_alt"],
            button_color=COLOR["border"], button_hover_color=COLOR["accent_dim"],
            text_color=COLOR["text"], font=label_font(12, "normal"),
            dropdown_fg_color=COLOR["surface_alt"], dropdown_hover_color=COLOR["accent_dim"],
            dropdown_text_color=COLOR["text"],
        )
        self.drop_fps.pack(fill="x")
        self.drop_fps.set("60 FPS")

    def _build_status_bar(self):
        wrap = ctk.CTkFrame(self.body, fg_color="transparent")
        wrap.pack(fill="x", pady=(2, 4))

        row = ctk.CTkFrame(wrap, fg_color="transparent")
        row.pack(fill="x")
        self.status_dot = StatusDot(row, size=9)
        self.status_dot.pack(side="left", padx=(2, 8))
        self.lbl_status = ctk.CTkLabel(row, text="App ready — paste a URL to begin.",
                                        font=label_font(11, "normal"), text_color=COLOR["text_muted"],
                                        anchor="w")
        self.lbl_status.pack(side="left", fill="x", expand=True)

        self.progress = ctk.CTkProgressBar(
            wrap, height=6, corner_radius=3, mode="indeterminate",
            fg_color=COLOR["surface_alt"], progress_color=COLOR["accent"],
        )
        self.progress.pack(fill="x", pady=(10, 0))
        self.progress.set(0)

    def _build_action_bar(self):
        wrap = ctk.CTkFrame(self.shell, fg_color=COLOR["surface"], corner_radius=0,
                             border_width=0)
        wrap.pack(fill="x", side="bottom")
        divider = ctk.CTkFrame(wrap, height=1, fg_color=COLOR["border"])
        divider.pack(fill="x")

        inner = ctk.CTkFrame(wrap, fg_color="transparent")
        inner.pack(fill="x", padx=22, pady=16)

        self.btn_clip = ctk.CTkButton(
            inner, text="Download Clip", font=label_font(13, "bold"), height=46,
            corner_radius=10, fg_color=COLOR["accent"], hover_color=COLOR["accent_hover"],
            text_color="#0B0C0E", command=lambda: self.launch_worker(get_full=False),
        )
        self.btn_clip.pack(fill="x", pady=(0, 10))

        self.btn_full = ctk.CTkButton(
            inner, text="Download Full Video", font=label_font(13, "bold"), height=46,
            corner_radius=10, fg_color="transparent", hover_color=COLOR["surface_alt"],
            border_width=1, border_color=COLOR["border"],
            text_color=COLOR["text"], command=lambda: self.launch_worker(get_full=True),
        )
        self.btn_full.pack(fill="x")

    # ------------------------------------------------------------- actions --

    def find_local_folder(self):
        chosen = filedialog.askdirectory(initialdir=self.clips_folder)
        if chosen:
            self.ent_loc.delete(0, "end")
            self.ent_loc.insert(0, os.path.normpath(chosen))

    def update_msg(self, msg, text_hex="#ffffff", dot=None):
        self.lbl_status.configure(text=msg, text_color=text_hex)
        if dot:
            self.status_dot.set_color(dot)
            self.header_dot.set_color(dot)

    def freeze_controls(self, state_val):
        self.btn_clip.configure(state=state_val)
        self.btn_full.configure(state=state_val)
        if state_val == "disabled":
            self.lbl_ready.configure(text="WORKING")
            self.progress.start()
        else:
            self.lbl_ready.configure(text="READY")
            self.progress.stop()
            self.progress.set(0)

    def launch_worker(self, get_full):
        self.freeze_controls("disabled")
        self.update_msg("Starting up…", COLOR["text_muted"], dot=COLOR["amber"])
        threading.Thread(target=self.grab_and_cut, args=(get_full,), daemon=True).start()

    def grab_and_cut(self, get_full):
        link = self.ent_url.get().strip()
        wanted_name = self.ent_file.get().strip()
        save_to = self.ent_loc.get().strip()
        t_start = self.ent_start.get().strip() or "00:01:00"
        t_end = self.ent_end.get().strip() or "00:01:30"

        if not os.path.exists(save_to):
            save_to = self.clips_folder

        picked_res = self.drop_res.get().split()[0]
        v_height = "2160" if "4K" in picked_res else "1440" if "2K" in picked_res else picked_res.replace("p", "")
        max_fps = self.drop_fps.get().split()[0]

        if not link:
            self.update_msg("Error: Missing target video URL link!", COLOR["danger"], dot=COLOR["danger"])
            self.freeze_controls("normal")
            return

        self.update_msg("Fetching layout formats from host stream…", COLOR["amber"], dot=COLOR["amber"])

        name_str = f"{wanted_name}.mp4" if wanted_name else f"stream_clip_{int(time.time())}.mp4"
        final_file_out = os.path.join(save_to, name_str)

        best_quality_string = f"bestvideo[height<={v_height}][fps<={max_fps}]+bestaudio/best[height<={v_height}]"

        dl_config = {
            'format': best_quality_string,
            'quiet': True,
            'no_warnings': True,
        }

        try:
            with YoutubeDL(dl_config) as engine:
                metadata = engine.extract_info(link, download=False)
                if 'requested_formats' in metadata:
                    stream_v_url = metadata['requested_formats'][0]['url']
                    stream_a_url = metadata['requested_formats'][1]['url']
                else:
                    stream_v_url = metadata['url']
                    stream_a_url = metadata['url']

            binary_ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
            no_window_flag = 0x08000000 if os.name == 'nt' else 0

            if get_full:
                self.update_msg("Merging complete video file data streams…", COLOR["amber"], dot=COLOR["amber"])
                args_list = [
                    binary_ffmpeg, '-y',
                    '-i', stream_v_url, '-i', stream_a_url,
                    '-map', '0:v:0', '-map', '1:a:0',
                    '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
                    final_file_out
                ]
            else:
                self.update_msg("Slicing clip to match requested range…", COLOR["amber"], dot=COLOR["amber"])
                args_list = [
                    binary_ffmpeg, '-y',
                    '-ss', t_start, '-i', stream_v_url,
                    '-ss', t_start, '-i', stream_a_url,
                    '-to', t_end,
                    '-map', '0:v:0', '-map', '1:a:0',
                    '-c:v', 'libx264', '-preset', 'fast', '-crf', '20',
                    '-c:a', 'aac', '-b:a', '192k', '-async', '1',
                    final_file_out
                ]

            execution = subprocess.run(
                args_list,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, creationflags=no_window_flag
            )

            if execution.returncode == 0:
                self.update_msg("Export done — file is in your chosen folder.", COLOR["mint"], dot=COLOR["mint"])

                clean_path_str = os.path.normpath(final_file_out)
                if os.name == 'nt':
                    subprocess.run(f'explorer /select,"{clean_path_str}"', creationflags=no_window_flag)
                else:
                    subprocess.run(["open", "-R", clean_path_str])
            else:
                self.update_msg("Extraction engine returned an error handling tracks.", COLOR["danger"], dot=COLOR["danger"])
                print(execution.stderr)

        except Exception as err:
            self.update_msg("Failed connection or parsing streams.", COLOR["danger"], dot=COLOR["danger"])
            print(err)

        self.freeze_controls("normal")


if __name__ == "__main__":
    app = StreamClipApp()
    app.mainloop()
