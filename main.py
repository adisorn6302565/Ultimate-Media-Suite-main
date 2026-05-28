import customtkinter as ctk
from tkinter import filedialog, messagebox
import os
import sys
import threading
import subprocess
import json
import time
import re
import traceback
import urllib.request
import io
import concurrent.futures
import logging
from PIL import Image

# --- ฟังก์ชันหา Path จริง ไม่ว่าจะรันแบบ .py หรือ .exe ---
def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)

def get_ytdlp_path():
    """Get yt-dlp.exe path, prioritizing updated version next to exe"""
    # Check if running as frozen executable
    if getattr(sys, 'frozen', False):
        # Check for updated yt-dlp.exe next to the main.exe
        app_dir = os.path.dirname(sys.executable)
        external_ytdlp = os.path.join(app_dir, "yt-dlp.exe")
        
        if os.path.exists(external_ytdlp):
            # Use the updated version next to exe
            return external_ytdlp
    
    # Use bundled version or fallback to system
    ytdlp_exe = resource_path(os.path.join("bin", "yt-dlp.exe"))
    if os.path.exists(ytdlp_exe):
        return ytdlp_exe
    
    # Fallback to system yt-dlp
    return "yt-dlp"

def get_ffmpeg_path():
    """Get ffmpeg.exe path from bin/"""
    ffmpeg_exe = resource_path(os.path.join("bin", "ffmpeg.exe"))
    if os.path.exists(ffmpeg_exe):
        return ffmpeg_exe
    return "ffmpeg" # Fallback

def get_ffprobe_path():
    """Get ffprobe.exe path from bin/"""
    ffprobe_exe = resource_path(os.path.join("bin", "ffprobe.exe"))
    if os.path.exists(ffprobe_exe):
        return ffprobe_exe
    return "ffprobe" # Fallback

# Configuration
APP_NAME = "Ultimate Media Suite"
VERSION = "1.3.2"
SETTINGS_FILE = "settings.json"
LOG_FILE = "ultimate_media_suite.log"
DOWNLOAD_MAX_WORKERS = 3
DOWNLOAD_MAX_ATTEMPTS = 2
BROWSER_COOKIE_MAP = {
    "Chrome": "chrome",
    "Edge": "edge",
    "Firefox": "firefox",
    "Opera": "opera",
    "Brave": "brave",
    "Vivaldi": "vivaldi",
    "Safari": "safari",
}
COOKIE_DATABASE_ERROR_RE = re.compile(
    r"Could not copy .*cookie database|cookie database.*locked|database is locked",
    re.IGNORECASE,
)
UNSUPPORTED_URL_RE = re.compile(r"Unsupported URL:\s*(\S+)", re.IGNORECASE)
FACEBOOK_COLLECTION_URL_RE = re.compile(
    r"^https?://(?:www\.|m\.)?facebook\.com/[^/?#]+/(?:reels|videos)/?(?:[?#].*)?$",
    re.IGNORECASE,
)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8"
)

# Set Theme
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class UltimateMediaSuite(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Window Setup
        self.title(f"{APP_NAME} v{VERSION}")
        self.geometry("1200x800")
        self.minsize(1000, 700)

        # Load Settings
        self.settings = self.load_settings()
        self.apply_settings()
        
        # Background GPU Encoders Detection
        self.supported_encoders = {"nvenc": False, "qsv": False, "amf": False}
        threading.Thread(target=self.detect_supported_encoders, daemon=True).start()
        
        # ThreadPool Executor for optimized background thumbnail loading
        self.thumbnail_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)
        
        # Download Process Tracking
        self.download_process = None
        self.is_downloading = False
        self.fetched_videos = []
        self.download_processes = {}
        self.download_lock = threading.Lock()
        self.download_cancelled = False
        self.failed_tasks = 0
        self.task_progress = {}
        
        # Convert Process Tracking
        self.convert_process = None
        self.is_converting = False
        
        # Parallel Download Tracking
        self.executor = None
        self.active_tasks = 0
        self.completed_tasks = 0
        self.total_tasks = 0

        # Grid Layout (1x2)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # Create Sidebar
        self.create_sidebar()

        # Create Content Area
        self.create_content_area()

        # Show Initial Page
        self.select_frame_by_name("downloader")
        
        # Auto-paste link if available
        self.after(800, self.auto_paste_link)
        
        # Check system tools on start
        self.after(500, self.check_all_tools)

    def load_settings(self):
        default_path = os.path.join(os.getcwd(), "Ultimate_Media_Output")
        if not os.path.exists(SETTINGS_FILE):
            return {"download_path": default_path, "browser_cookie": "None", "theme": "Dark", "max_workers": 3}
        try:
            with open(SETTINGS_FILE, "r", encoding='utf-8') as f:
                settings = json.load(f)
                if not settings.get("download_path"):
                    settings["download_path"] = default_path
                if "max_workers" not in settings:
                    settings["max_workers"] = 3
                return settings
        except:
            return {"download_path": default_path, "browser_cookie": "None", "theme": "Dark", "max_workers": 3}

    def save_settings(self):
        try:
            with open(SETTINGS_FILE, "w", encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def apply_settings(self):
        ctk.set_appearance_mode(self.settings.get("theme", "Dark"))

    def create_sidebar(self):
        self.sidebar_frame = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(5, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="🚀 MEDIA SUITE", font=ctk.CTkFont(size=22, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(30, 20))

        # Sidebar Buttons with modern style
        self.sidebar_button_1 = ctk.CTkButton(self.sidebar_frame, text="  📥 Downloader", height=40, anchor="w",
                                            command=lambda: self.select_frame_by_name("downloader"), 
                                            font=ctk.CTkFont(size=14))
        self.sidebar_button_1.grid(row=1, column=0, padx=20, pady=10, sticky="ew")

        self.sidebar_button_2 = ctk.CTkButton(self.sidebar_frame, text="  🔄 Converter", height=40, anchor="w",
                                            command=lambda: self.select_frame_by_name("converter"),
                                            font=ctk.CTkFont(size=14))
        self.sidebar_button_2.grid(row=2, column=0, padx=20, pady=10, sticky="ew")

        self.sidebar_button_3 = ctk.CTkButton(self.sidebar_frame, text="  ⚙️ Settings", height=40, anchor="w",
                                            command=lambda: self.select_frame_by_name("settings"),
                                            font=ctk.CTkFont(size=14))
        self.sidebar_button_3.grid(row=3, column=0, padx=20, pady=10, sticky="ew")

        # Bottom Info Area
        self.info_area = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.info_area.grid(row=6, column=0, padx=20, pady=20, sticky="ew")
        
        self.yt_status_label = ctk.CTkLabel(self.info_area, text="yt-dlp: Checking...", font=ctk.CTkFont(size=11))
        self.yt_status_label.pack(anchor="w")
        
        self.ffmpeg_status_label = ctk.CTkLabel(self.info_area, text="FFmpeg: Checking...", font=ctk.CTkFont(size=11))
        self.ffmpeg_status_label.pack(anchor="w")
        
        self.version_label = ctk.CTkLabel(self.info_area, text=f"Version: {VERSION}", text_color="gray", font=ctk.CTkFont(size=10))
        self.version_label.pack(anchor="w", pady=(10, 0))

    def create_content_area(self):
        # Create frames for each page
        self.downloader_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.converter_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.settings_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")

        # Build UI for each frame
        self.build_downloader_ui()
        self.build_converter_ui()
        self.build_settings_ui()
        self.normalize_ui_texts()

    def normalize_ui_texts(self):
        """Keep visible UI text readable even if older source strings are mojibake."""
        text_updates = [
            (self.logo_label, {"text": "MEDIA SUITE"}),
            (self.sidebar_button_1, {"text": "  Downloader"}),
            (self.sidebar_button_2, {"text": "  Converter"}),
            (self.sidebar_button_3, {"text": "  Settings"}),
            (self.url_entry, {"placeholder_text": "Paste a link from YouTube, Facebook, Instagram, TikTok..."}),
            (self.paste_btn, {"text": "Paste"}),
            (self.analyze_btn, {"text": "Analyze"}),
            (self.remove_btn, {"text": "Remove Selected"}),
            (self.clear_btn, {"text": "Clear All"}),
            (self.search_entry, {"placeholder_text": "Filter videos by title..."}),
            (self.cancel_btn, {"text": "STOP"}),
            (self.open_folder_btn, {"text": "Open"}),
            (self.conv_input_entry, {"placeholder_text": "Choose a media file to convert..."}),
            (self.gpu_accel_chk, {"text": "Enable GPU Acceleration (Fastest)"}),
            (self.conv_cancel_btn, {"text": "CANCEL"}),
            (self.save_settings_btn, {"text": "SAVE SETTINGS"}),
            (self.update_btn, {"text": "UPDATE TOOLS"})
        ]

        for widget, options in text_updates:
            widget.configure(**options)

    def select_frame_by_name(self, name):
        # set button color for selected button
        self.sidebar_button_1.configure(fg_color=("gray75", "gray25") if name == "downloader" else "transparent")
        self.sidebar_button_2.configure(fg_color=("gray75", "gray25") if name == "converter" else "transparent")
        self.sidebar_button_3.configure(fg_color=("gray75", "gray25") if name == "settings" else "transparent")

        # show selected frame
        if name == "downloader":
            self.downloader_frame.grid(row=0, column=1, sticky="nsew")
        else:
            self.downloader_frame.grid_forget()
        
        if name == "converter":
            self.converter_frame.grid(row=0, column=1, sticky="nsew")
        else:
            self.converter_frame.grid_forget()

        if name == "settings":
            self.settings_frame.grid(row=0, column=1, sticky="nsew")
        else:
            self.settings_frame.grid_forget()

    def _legacy_check_all_tools(self):
        # Check yt-dlp
        ytdlp = get_ytdlp_path()
        if os.path.exists(ytdlp) or self.is_tool("yt-dlp"):
             self.yt_status_label.configure(text="✅ yt-dlp: Ready", text_color="green")
        else:
             self.yt_status_label.configure(text="❌ yt-dlp: Missing", text_color="orange")
             
        # Check FFmpeg
        ffmpeg = get_ffmpeg_path()
        if os.path.exists(ffmpeg) or self.is_tool("ffmpeg"):
             self.ffmpeg_status_label.configure(text="✅ FFmpeg: Ready", text_color="green")
        else:
             self.ffmpeg_status_label.configure(text="❌ FFmpeg: Missing", text_color="orange")

    def is_tool(self, name):
        from shutil import which
        return which(name) is not None

    def check_all_tools(self):
        ytdlp = get_ytdlp_path()
        if os.path.exists(ytdlp) or self.is_tool("yt-dlp"):
            self.yt_status_label.configure(text="yt-dlp: Ready", text_color="green")
        else:
            self.yt_status_label.configure(text="yt-dlp: Missing", text_color="orange")

        ffmpeg = get_ffmpeg_path()
        if os.path.exists(ffmpeg) or self.is_tool("ffmpeg"):
            self.ffmpeg_status_label.configure(text="FFmpeg: Ready", text_color="green")
        else:
            self.ffmpeg_status_label.configure(text="FFmpeg: Missing", text_color="orange")

    def detect_supported_encoders(self):
        try:
            ffmpeg = get_ffmpeg_path()
            res = subprocess.run(
                [ffmpeg, "-encoders"],
                capture_output=True,
                text=True,
                errors="ignore",
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            self.supported_encoders["nvenc"] = "h264_nvenc" in res.stdout
            self.supported_encoders["qsv"] = "h264_qsv" in res.stdout
            self.supported_encoders["amf"] = "h264_amf" in res.stdout
            logging.info("GPU hardware encoders detected: %s", self.supported_encoders)
        except Exception:
            logging.exception("Failed to detect GPU encoders")

    # --- UI Builders ---
    def build_downloader_ui(self):
        # Zone A: Input & Analyze
        self.dl_header = ctk.CTkLabel(self.downloader_frame, text="Download Video & Audio", font=ctk.CTkFont(size=24, weight="bold"))
        self.dl_header.pack(anchor="w", padx=30, pady=(30, 10))

        self.zone_a_frame = ctk.CTkFrame(self.downloader_frame)
        self.zone_a_frame.pack(fill="x", padx=30, pady=10)

        # URL Input
        self.url_input_frame = ctk.CTkFrame(self.zone_a_frame, fg_color="transparent")
        self.url_input_frame.pack(fill="x", padx=15, pady=20)
        
        self.url_entry = ctk.CTkEntry(self.url_input_frame, placeholder_text="วางลิงก์จาก YouTube, FB, IG, TikTok...", height=45, font=ctk.CTkFont(size=14))
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.paste_btn = ctk.CTkButton(self.url_input_frame, text="📋 Paste", width=100, height=45, command=self.paste_url, fg_color="gray25", hover_color="gray35")
        self.paste_btn.pack(side="left", padx=5)

        self.analyze_btn = ctk.CTkButton(self.url_input_frame, text="🔍 Analyze", width=120, height=45, fg_color="#1f538d", hover_color="#14375e", command=self.analyze_url)
        self.analyze_btn.pack(side="left", padx=5)

        # Options
        self.dl_options_row = ctk.CTkFrame(self.zone_a_frame, fg_color="transparent")
        self.dl_options_row.pack(fill="x", padx=15, pady=(0, 15))
        
        self.profile_mode_var = ctk.BooleanVar(value=False)
        self.profile_chk = ctk.CTkCheckBox(self.dl_options_row, text="Playlist / Profile Mode", variable=self.profile_mode_var)
        self.profile_chk.pack(side="left", padx=(0, 20))
        
        self.thumb_only_var = ctk.BooleanVar(value=False)
        self.thumb_chk = ctk.CTkCheckBox(self.dl_options_row, text="Download Thumbnails", variable=self.thumb_only_var)
        self.thumb_chk.pack(side="left", padx=10)

        # Zone B: List Area
        self.zone_b_frame = ctk.CTkFrame(self.downloader_frame)
        self.zone_b_frame.pack(fill="both", expand=True, padx=30, pady=10)

        self.list_controls = ctk.CTkFrame(self.zone_b_frame, fg_color="transparent")
        self.list_controls.pack(fill="x", padx=10, pady=5)
        
        self.remove_btn = ctk.CTkButton(self.list_controls, text="🗑️ Remove Selected", width=140, fg_color="#a13333", hover_color="#7b2626", height=28, command=self.remove_selected_videos)
        self.remove_btn.pack(side="left", padx=5)
        
        self.clear_btn = ctk.CTkButton(self.list_controls, text="🧹 Clear All", width=100, fg_color="gray30", height=28, command=self.clear_video_list)
        self.clear_btn.pack(side="left", padx=5)

        self.select_all_var = ctk.BooleanVar(value=True)
        self.select_all_chk = ctk.CTkSwitch(self.list_controls, text="Select All", variable=self.select_all_var, command=self.toggle_select_all)
        self.select_all_chk.pack(side="right", padx=10)

        self.video_list_frame = ctk.CTkScrollableFrame(self.zone_b_frame, label_text="Videos to Download (0 items)")
        self.video_list_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # Search Filter
        self.search_row = ctk.CTkFrame(self.zone_b_frame, fg_color="transparent")
        self.search_row.pack(fill="x", padx=10, pady=(0, 5))
        self.search_entry = ctk.CTkEntry(self.search_row, placeholder_text="🔍 Filter videos by title...", height=30)
        self.search_entry.pack(fill="x", padx=5)
        self.search_entry.bind("<KeyRelease>", self.filter_video_list)

        # Zone C: Footer Configuration
        self.zone_c_frame = ctk.CTkFrame(self.downloader_frame)
        self.zone_c_frame.pack(fill="x", padx=30, pady=(10, 30))

        # Config row
        self.config_row = ctk.CTkFrame(self.zone_c_frame, fg_color="transparent")
        self.config_row.pack(fill="x", padx=20, pady=15)
        
        ctk.CTkLabel(self.config_row, text="Format:").pack(side="left", padx=(0, 10))
        self.format_combo = ctk.CTkComboBox(self.config_row, values=["MP4 (Video)", "MKV (Video)", "MP3 (Audio)", "WAV (Audio)"], command=self.update_quality_options, width=180)
        self.format_combo.pack(side="left", padx=10)
        self.format_combo.set("MP4 (Video)")

        ctk.CTkLabel(self.config_row, text="Quality:").pack(side="left", padx=(20, 10))
        self.quality_combo = ctk.CTkComboBox(self.config_row, values=["Best Available", "4K (2160p)", "2K (1440p)", "1080p", "720p", "480p", "360p"], width=180)
        self.quality_combo.pack(side="left", padx=10)
        self.quality_combo.set("Best Available")

        # Progress row
        self.progress_frame = ctk.CTkFrame(self.zone_c_frame, fg_color="transparent")
        self.progress_frame.pack(fill="x", padx=20, pady=(0, 10))
        
        self.progress_bar = ctk.CTkProgressBar(self.progress_frame, height=12)
        self.progress_bar.pack(fill="x", pady=10)
        self.progress_bar.set(0)

        self.status_labels = ctk.CTkFrame(self.progress_frame, fg_color="transparent")
        self.status_labels.pack(fill="x")
        
        self.speed_label = ctk.CTkLabel(self.status_labels, text="Speed: --", font=ctk.CTkFont(size=12))
        self.speed_label.pack(side="left")
        
        self.eta_label = ctk.CTkLabel(self.status_labels, text="ETA: --", font=ctk.CTkFont(size=12), padx=20)
        self.eta_label.pack(side="left")
        
        self.size_label = ctk.CTkLabel(self.status_labels, text="Size: --", font=ctk.CTkFont(size=12))
        self.size_label.pack(side="left")

        # Action Button
        self.button_row = ctk.CTkFrame(self.zone_c_frame, fg_color="transparent")
        self.button_row.pack(fill="x", padx=20, pady=(10, 20))
        
        self.start_btn = ctk.CTkButton(self.button_row, text="START DOWNLOAD", height=50, fg_color="#28a745", hover_color="#218838", 
                                     font=ctk.CTkFont(size=18, weight="bold"), command=self.start_download)
        self.start_btn.pack(side="left", expand=True, fill="x", padx=(0, 10))
        
        self.cancel_btn = ctk.CTkButton(self.button_row, text="⏹ STOP", height=50, fg_color="#dc3545", hover_color="#c82333",
                                      font=ctk.CTkFont(size=18, weight="bold"), command=self.cancel_download)
        self.cancel_btn.pack(side="left", expand=True, fill="x")
        self.cancel_btn.pack_forget()

        self.open_folder_btn = ctk.CTkButton(self.button_row, text="📂", width=60, height=50, fg_color="gray30", command=self.open_output_folder)
        self.open_folder_btn.pack(side="right", padx=(10, 0))

    def build_converter_ui(self):
        self.conv_header = ctk.CTkLabel(self.converter_frame, text="Media Converter", font=ctk.CTkFont(size=24, weight="bold"))
        self.conv_header.pack(anchor="w", padx=30, pady=(30, 10))

        # Selection Box
        self.conv_box = ctk.CTkFrame(self.converter_frame)
        self.conv_box.pack(fill="x", padx=30, pady=10)

        self.conv_input_row = ctk.CTkFrame(self.conv_box, fg_color="transparent")
        self.conv_input_row.pack(fill="x", padx=20, pady=30)
        
        self.conv_input_entry = ctk.CTkEntry(self.conv_input_row, placeholder_text="เลือกไฟล์ที่ต้องการแปลง...", height=40)
        self.conv_input_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        self.conv_browse_btn = ctk.CTkButton(self.conv_input_row, text="Browse File", width=120, height=40, command=self.browse_input_file)
        self.conv_browse_btn.pack(side="left")

        # Format & Quality
        self.conv_opt_box = ctk.CTkFrame(self.converter_frame)
        self.conv_opt_box.pack(fill="x", padx=30, pady=10)
        
        self.conv_opt_row = ctk.CTkFrame(self.conv_opt_box, fg_color="transparent")
        self.conv_opt_row.pack(fill="x", padx=20, pady=20)
        
        ctk.CTkLabel(self.conv_opt_row, text="Target Format:").pack(side="left", padx=(0, 10))
        self.conv_format_combo = ctk.CTkComboBox(self.conv_opt_row, values=["MP3 (Audio)", "WAV (Audio)", "MP4 (Video)", "MKV (Video)", "GIF (Image/Anim)", "FLAC", "AAC", "WEBM"], width=180)
        self.conv_format_combo.pack(side="left", padx=10)
        self.conv_format_combo.set("MP3 (Audio)")

        ctk.CTkLabel(self.conv_opt_row, text="Quality:").pack(side="left", padx=(20, 10))
        self.conv_quality_combo = ctk.CTkComboBox(self.conv_opt_row, values=["Ultra (High)", "Normal (Medium)", "Small (Low)"], width=180)
        self.conv_quality_combo.pack(side="left", padx=10)
        self.conv_quality_combo.set("Normal (Medium)")
        
        self.gpu_accel_var = ctk.BooleanVar(value=True)
        self.gpu_accel_chk = ctk.CTkCheckBox(self.conv_opt_box, text="🚀 Enable GPU Acceleration (Fastest)", variable=self.gpu_accel_var)
        self.gpu_accel_chk.pack(anchor="w", padx=20, pady=(0, 20))

        # Converter Actions
        self.conv_action_box = ctk.CTkFrame(self.converter_frame)
        self.conv_action_box.pack(fill="x", padx=30, pady=10)
        
        self.conv_status_label = ctk.CTkLabel(self.conv_action_box, text="Ready to convert", font=ctk.CTkFont(size=14))
        self.conv_status_label.pack(pady=(20, 5))
        
        self.conv_progress = ctk.CTkProgressBar(self.conv_action_box, height=12)
        self.conv_progress.pack(fill="x", padx=40, pady=10)
        self.conv_progress.set(0)

        self.convert_btn = ctk.CTkButton(self.conv_action_box, text="CONVERT NOW", height=50, fg_color="#007bff", hover_color="#0069d9",
                                        font=ctk.CTkFont(size=18, weight="bold"), command=self.convert_media)
        self.convert_btn.pack(fill="x", padx=40, pady=(20, 30))
        
        self.conv_cancel_btn = ctk.CTkButton(self.conv_action_box, text="⏹ CANCEL", height=50, fg_color="#dc3545", hover_color="#c82333",
                                           font=ctk.CTkFont(size=18, weight="bold"), command=self.cancel_conversion)
        self.conv_cancel_btn.pack(fill="x", padx=40, pady=(20, 30))
        self.conv_cancel_btn.pack_forget()

    def build_settings_ui(self):
        self.set_header = ctk.CTkLabel(self.settings_frame, text="Application Settings", font=ctk.CTkFont(size=24, weight="bold"))
        self.set_header.pack(anchor="w", padx=30, pady=(30, 20))

        # Output Path
        self.s_path_box = ctk.CTkFrame(self.settings_frame)
        self.s_path_box.pack(fill="x", padx=30, pady=10)
        
        ctk.CTkLabel(self.s_path_box, text="📁 Default Storage Path", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=20, pady=(20, 10))
        
        self.path_row = ctk.CTkFrame(self.s_path_box, fg_color="transparent")
        self.path_row.pack(fill="x", padx=20, pady=(0, 20))
        
        self.output_path_entry = ctk.CTkEntry(self.path_row)
        self.output_path_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.output_path_entry.insert(0, self.settings.get("download_path", ""))

        self.browse_path_btn = ctk.CTkButton(self.path_row, text="Browse", width=100, command=self.browse_output_folder)
        self.browse_path_btn.pack(side="left")

        # Cookies / Browser
        self.s_cookie_box = ctk.CTkFrame(self.settings_frame)
        self.s_cookie_box.pack(fill="x", padx=30, pady=10)
        
        ctk.CTkLabel(self.s_cookie_box, text="🍪 Browser Cookies (For FB/IG Restricted Content)", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=20, pady=(20, 5))
        ctk.CTkLabel(self.s_cookie_box, text="เลือกเบราว์เซอร์ที่เข้าสู่ระบบ Facebook/Instagram ไว้ เพื่อให้ดาวน์โหลดคลิปส่วนตัวได้", text_color="gray").pack(anchor="w", padx=20, pady=(0, 15))
        
        self.cookie_combo = ctk.CTkComboBox(self.s_cookie_box, values=["None", "Chrome", "Edge", "Firefox", "Opera", "Brave", "Vivaldi", "Safari"], width=250)
        self.cookie_combo.pack(anchor="w", padx=20, pady=(0, 25))
        self.cookie_combo.set(self.settings.get("browser_cookie", "None"))

        # Max Workers Box
        self.s_workers_box = ctk.CTkFrame(self.settings_frame)
        self.s_workers_box.pack(fill="x", padx=30, pady=10)
        
        ctk.CTkLabel(self.s_workers_box, text="⚡ Max Concurrent Downloads", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=20, pady=(20, 5))
        ctk.CTkLabel(self.s_workers_box, text="จำนวนดาวน์โหลดพร้อมกันสูงสุด (ค่าเริ่มต้น: 3, แนะนำ 1-5)", text_color="gray").pack(anchor="w", padx=20, pady=(0, 15))
        
        self.workers_combo = ctk.CTkComboBox(self.s_workers_box, values=["1", "2", "3", "4", "5", "6", "8", "10"], width=250)
        self.workers_combo.pack(anchor="w", padx=20, pady=(0, 25))
        self.workers_combo.set(str(self.settings.get("max_workers", 3)))

        # Theme
        self.s_theme_box = ctk.CTkFrame(self.settings_frame)
        self.s_theme_box.pack(fill="x", padx=30, pady=10)
        
        ctk.CTkLabel(self.s_theme_box, text="🎨 Appearance", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=20, pady=(20, 10))
        
        self.theme_switch_var = ctk.StringVar(value=self.settings.get("theme", "Dark"))
        self.theme_switch = ctk.CTkSwitch(self.s_theme_box, text="Dark Mode", command=self.change_theme, variable=self.theme_switch_var, onvalue="Dark", offvalue="Light")
        self.theme_switch.pack(anchor="w", padx=20, pady=(0, 25))

        # Bottom Actions
        self.s_footer = ctk.CTkFrame(self.settings_frame, fg_color="transparent")
        self.s_footer.pack(fill="x", padx=30, pady=(20, 30), side="bottom")
        
        self.save_settings_btn = ctk.CTkButton(self.s_footer, text="💾 SAVE SETTINGS", height=50, fg_color="#28a745", hover_color="#218838",
                                             font=ctk.CTkFont(size=16, weight="bold"), command=self.save_settings_from_ui)
        self.save_settings_btn.pack(side="left", expand=True, fill="x", padx=(0, 10))
        
        self.update_btn = ctk.CTkButton(self.s_footer, text="🔄 UPDATE TOOLS", height=50, fg_color="#17a2b8", hover_color="#138496", 
                                      font=ctk.CTkFont(size=14), command=self.update_frameworks)
        self.update_btn.pack(side="left", expand=True, fill="x")

    # --- Logic Methods ---
    def paste_url(self):
        try:
            self.url_entry.delete(0, "end")
            self.url_entry.insert(0, self.clipboard_get())
        except:
            pass

    def _browser_cookie_args(self, browser_ui):
        browser = BROWSER_COOKIE_MAP.get(browser_ui or "None")
        if not browser:
            return []
        return ["--cookies-from-browser", browser]

    def _is_cookie_database_error(self, message):
        return bool(COOKIE_DATABASE_ERROR_RE.search(message or ""))

    def _is_unsupported_url_error(self, message):
        return bool(UNSUPPORTED_URL_RE.search(message or ""))

    def _is_facebook_collection_url(self, url):
        return bool(FACEBOOK_COLLECTION_URL_RE.search(url or ""))

    def _clean_tool_error(self, message):
        lines = []
        seen = set()
        for raw_line in (message or "").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line in seen:
                continue
            seen.add(line)
            lines.append(line)
        return "\n".join(lines)

    def _cookie_retry_message(self, browser_ui):
        return (
            f"Could not read cookies from {browser_ui}.\n\n"
            "The app retried without browser cookies. If you need private/restricted content, "
            "close the browser completely and try again, or set Settings > Browser Cookies to None."
        )

    def _cookie_failure_message(self, browser_ui, detail):
        cleaned = self._clean_tool_error(detail)
        message = (
            f"Could not read cookies from {browser_ui}.\n\n"
            "Close all browser windows and background processes, then try again. "
            "For public videos, choose Settings > Browser Cookies = None."
        )
        if cleaned:
            message += f"\n\nDetails:\n{cleaned}"
        return message

    def _facebook_collection_message(self):
        return (
            "ลิงก์นี้เป็นหน้ารวม Reels/Videos ของ Facebook ไม่ใช่ลิงก์คลิปโดยตรง\n\n"
            "yt-dlp ยังไม่รองรับการดึงทั้งหน้าแบบนี้ ให้เปิดคลิปที่ต้องการก่อน "
            "แล้วคัดลอกลิงก์ของคลิปนั้นมาใส่แทน เช่น:\n"
            "facebook.com/reel/...\n"
            "หรือ facebook.com/watch/?v=..."
        )

    def _analysis_failure_message(self, url, detail, retried_without_cookies=False, browser_ui="None"):
        cleaned = self._clean_tool_error(detail)
        prefix = ""
        if retried_without_cookies and browser_ui in BROWSER_COOKIE_MAP:
            prefix = f"Could not read cookies from {browser_ui}, so the app retried without browser cookies.\n\n"

        if self._is_unsupported_url_error(cleaned):
            if self._is_facebook_collection_url(url):
                message = self._facebook_collection_message()
            else:
                message = "This link type is not supported by yt-dlp. Please paste a direct video link."

            if cleaned:
                message += f"\n\nDetails:\n{cleaned}"
            return prefix + message

        if self._is_cookie_database_error(cleaned):
            return self._cookie_failure_message(browser_ui, cleaned)

        return prefix + (cleaned or "Analysis failed.")

    def _build_analyze_command(self, url, is_profile_mode, browser_ui=None):
        cmd = [get_ytdlp_path(), "--dump-json", "--skip-download", "--flat-playlist"]
        cmd.append("--yes-playlist" if is_profile_mode else "--no-playlist")
        cmd.extend(self._browser_cookie_args(browser_ui))
        cmd.append(url)
        return cmd

    def _run_analyze_command(self, cmd):
        logging.info("Analyze command: %s", " ".join(cmd))
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="ignore",
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )

        found_any = False
        count = 0

        for line in process.stdout:
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                logging.debug("Skipping non-json analyze output: %s", line.strip())
                continue

            count += 1
            found_any = True
            self.after(0, lambda d=data, c=count: self.add_video_to_list_progress(d, c))

        process.wait()
        stderr = process.stderr.read()
        if stderr:
            logging.info("Analyze stderr: %s", stderr.strip())

        return process.returncode, found_any, stderr

    def _legacy_analyze_url(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Warning", "กรุณาวางลิงก์ที่ต้องการวิเคราะห์")
            return

        self.analyze_btn.configure(state="disabled", text="⌛ Analyzing...")
        
        # Clear existing items and search
        for widget in self.video_list_frame.winfo_children():
            widget.destroy()
        self.fetched_videos = []
        self.search_entry.delete(0, "end")
        self.video_list_frame.configure(label_text="Videos to Download (0 items)")

        is_profile_mode = self.profile_mode_var.get()
        threading.Thread(target=self._analyze_thread, args=(url, is_profile_mode), daemon=True).start()

    def _legacy_analyze_thread(self, url, is_profile_mode):
        try:
            ytdlp_exe = get_ytdlp_path()
            cmd = [ytdlp_exe, "--dump-json", "--skip-download", "--flat-playlist"]
            
            if is_profile_mode:
                cmd.append("--yes-playlist")
            else:
                cmd.append("--no-playlist")
            
            # Cookies
            browser_map = {"Chrome":"chrome", "Edge":"edge", "Firefox":"firefox", "Opera":"opera", "Brave":"brave", "Vivaldi":"vivaldi", "Safari":"safari"}
            browser_ui = self.settings.get("browser_cookie", "None")
            if browser_ui in browser_map:
                cmd.extend(["--cookies-from-browser", browser_map[browser_ui]])
            
            cmd.append(url)
            
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='ignore', creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
            
            found_any = False
            count = 0
            
            # Process output line by line as it arrives
            while True:
                line = process.stdout.readline()
                if not line:
                    break
                    
                try:
                    data = json.loads(line)
                    count += 1
                    self.after(0, lambda d=data, c=count: self.add_video_to_list_progress(d, c))
                    found_any = True
                except:
                    pass
            
            process.wait()
            stderr = process.stderr.read()

            if process.returncode != 0 and not found_any:
                raise Exception(stderr or "เกิดข้อผิดพลาดในการวิเคราะห์")

            if not found_any:
                 raise Exception("ไม่พบข้อมูลวิดีโอจากลิงก์นี้")

            self.after(0, lambda: self.analyze_btn.configure(state="normal", text="🔍 Analyze (Done)"))
            self.after(2000, lambda: self.analyze_btn.configure(text="🔍 Analyze"))

        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Error", f"เกิดข้อผิดพลาดในการวิเคราะห์:\n{str(e)}"))
            self.after(0, lambda: self.analyze_btn.configure(state="normal", text="🔍 Analyze"))

    def _legacy_add_video_to_list_progress(self, data, count):
        """Update button text to show progress and add item"""
        self.analyze_btn.configure(text=f"⌛ Analyzing... ({count})")
        self.add_video_to_list(data)
        count_curr = len(self.fetched_videos)
        self.after(0, lambda: self.video_list_frame.configure(label_text=f"Videos to Download ({count_curr} items)"))

    def analyze_url(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Warning", "Please paste a link to analyze.")
            return
        if self._is_facebook_collection_url(url):
            messagebox.showwarning("Facebook link not supported", self._facebook_collection_message())
            return

        self.analyze_btn.configure(state="disabled", text="Analyzing...")

        for widget in self.video_list_frame.winfo_children():
            widget.destroy()
        self.fetched_videos = []
        self.search_entry.delete(0, "end")
        self.video_list_frame.configure(label_text="Videos to Download (0 items)")

        threading.Thread(
            target=self._analyze_thread,
            args=(url, self.profile_mode_var.get()),
            daemon=True
        ).start()

    def _analyze_thread(self, url, is_profile_mode):
        try:
            browser_ui = self.settings.get("browser_cookie", "None")
            cmd = self._build_analyze_command(url, is_profile_mode, browser_ui)
            returncode, found_any, stderr = self._run_analyze_command(cmd)

            retried_without_cookies = False
            if (
                returncode != 0
                and not found_any
                and browser_ui in BROWSER_COOKIE_MAP
                and self._is_cookie_database_error(stderr)
            ):
                retried_without_cookies = True
                logging.warning("Browser cookie read failed for %s; retrying analyze without cookies", browser_ui)
                fallback_cmd = self._build_analyze_command(url, is_profile_mode, "None")
                returncode, found_any, fallback_stderr = self._run_analyze_command(fallback_cmd)
                stderr = fallback_stderr or stderr

            if returncode != 0 and not found_any:
                raise Exception(
                    self._analysis_failure_message(
                        url,
                        stderr,
                        retried_without_cookies=retried_without_cookies,
                        browser_ui=browser_ui
                    )
                )

            if not found_any:
                raise Exception("No video data found for this link.")

            self.after(0, lambda: self.analyze_btn.configure(state="normal", text="Analyze (Done)"))
            self.after(2000, lambda: self.analyze_btn.configure(text="Analyze"))
            if retried_without_cookies:
                self.after(0, lambda: messagebox.showwarning("Browser Cookies skipped", self._cookie_retry_message(browser_ui)))
        except Exception as e:
            logging.exception("Analysis failed")
            self.after(0, lambda: messagebox.showerror("Error", f"Analysis failed:\n{str(e)}"))
            self.after(0, lambda: self.analyze_btn.configure(state="normal", text="Analyze"))

    def add_video_to_list_progress(self, data, count):
        self.analyze_btn.configure(text=f"Analyzing... ({count})")
        self.add_video_to_list(data)
        count_curr = len(self.fetched_videos)
        self.video_list_frame.configure(label_text=f"Videos to Download ({count_curr} items)")

    def _on_analyze_complete(self, videos):
        # This is no longer used for sequential adding, but kept for compatibility if needed
        pass

    def add_video_to_list(self, video_data):
        row = ctk.CTkFrame(self.video_list_frame, fg_color=("gray90", "gray15"))
        row.pack(fill="x", padx=5, pady=2)

        chk_var = ctk.BooleanVar(value=True)
        chk = ctk.CTkCheckBox(row, text="", variable=chk_var, width=20)
        chk.pack(side="left", padx=10)
        
        # Thumbnail
        thumb_label = ctk.CTkLabel(row, text="🖼️", width=100, height=60, fg_color="black", corner_radius=5)
        thumb_label.pack(side="left", padx=5, pady=5)
        
        thumb_url = video_data.get("thumbnail")
        if thumb_url:
             self.thumbnail_executor.submit(self._load_thumbnail, thumb_url, thumb_label)
        
        # Info
        title = video_data.get("title", "Unknown Video")
        if len(title) > 60: title = title[:57] + "..."
        
        duration = video_data.get("duration", 0)
        duration_str = time.strftime('%M:%S', time.gmtime(duration)) if duration else "--:--"
        uploader = video_data.get("uploader", "N/A")
        
        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True, padx=10)
        
        title_label = ctk.CTkLabel(info, text=title, anchor="w", font=ctk.CTkFont(weight="bold"))
        title_label.pack(fill="x")
        status_label = ctk.CTkLabel(info, text="Ready", anchor="w", text_color="gray", font=ctk.CTkFont(size=11))
        status_label.pack(fill="x")
        ctk.CTkLabel(info, text=f"👤 {uploader}  |  🕒 {duration_str}", anchor="w", text_color="gray").pack(fill="x")
        
        # Action Button (Preview)
        preview_btn = ctk.CTkButton(row, text="📺 Play", width=60, height=28, fg_color="gray30", command=lambda u=video_data.get("webpage_url") or video_data.get("url"): self.open_link(u))
        preview_btn.pack(side="right", padx=10)

        self.fetched_videos.append({
            "data": video_data,
            "var": chk_var,
            "frame": row,
            "title": title.lower(),
            "status_label": status_label
        })

    def _load_thumbnail(self, url, label):
        try:
            # Add User-Agent to prevent 403 Forbidden errors
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as u:
                raw = u.read()
            img = Image.open(io.BytesIO(raw))
            img.thumbnail((200, 150))
            
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(100, 60))
            self.after(0, lambda: label.configure(image=ctk_img, text=""))
            # Holding reference to avoid GC
            label._img_ref = ctk_img
        except Exception as e:
            print(f"Thumbnail load error: {e}")
            self.after(0, lambda: label.configure(text="No Image"))

    def remove_selected_videos(self):
        survivors = []
        for v in self.fetched_videos:
            if v["var"].get():
                v["frame"].destroy()
            else:
                survivors.append(v)
        self.fetched_videos = survivors
        count_curr = len(self.fetched_videos)
        self.after(0, lambda: self.video_list_frame.configure(label_text=f"Videos to Download ({count_curr} items)"))

    def clear_video_list(self):
        for v in self.fetched_videos:
            v["frame"].destroy()
        self.fetched_videos = []

    def toggle_select_all(self):
        state = self.select_all_var.get()
        for v in self.fetched_videos:
            v["var"].set(state)

    def update_quality_options(self, choice):
        if "Audio" in choice:
            self.quality_combo.configure(values=["Ultra (320kbps)", "High (256kbps)", "Normal (128kbps)"])
            self.quality_combo.set("Ultra (320kbps)")
        else:
            self.quality_combo.configure(values=["Best Available", "4K (2160p)", "2K (1440p)", "1080p", "720p", "480p", "360p"])
            self.quality_combo.set("Best Available")

    def _legacy_start_download(self):
        selected = [v for v in self.fetched_videos if v["var"].get()]
        if not selected:
            messagebox.showwarning("Warning", "กรุณาเลือกวิดีโออย่างน้อย 1 รายการ")
            return

        self.is_downloading = True
        self.start_btn.pack_forget()
        self.cancel_btn.pack(side="left", expand=True, fill="x")
        self.progress_bar.set(0)
        
        urls = [v["data"].get("webpage_url") or v["data"].get("url") for v in selected]
        self.total_tasks = len(urls)
        self.completed_tasks = 0
        
        self.status_label_top = ctk.CTkLabel(self.progress_frame, text=f"Progress: 0 / {self.total_tasks} completed", font=ctk.CTkFont(size=13, weight="bold"))
        self.status_label_top.pack(side="top", pady=(0, 5))
        
        threading.Thread(target=self._parallel_download_manager, args=(urls,), daemon=True).start()

    def _legacy_parallel_download_manager(self, urls):
        max_workers = 3
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            self.executor = executor
            futures = [executor.submit(self._single_download_task, url, i) for i, url in enumerate(urls)]
            for future in concurrent.futures.as_completed(futures):
                if not self.is_downloading: break
                try: 
                    future.result()
                    self.completed_tasks += 1
                    self.after(0, self._update_overall_progress)
                except Exception as e:
                    print(f"Task error: {e}")
        
        self.is_downloading = False
        self.after(0, self._reset_download_ui)
        self.after(0, lambda: messagebox.showinfo("สำเร็จ", f"ดาวน์โหลดเสร็จสิ้น!\nเสร็จทั้งหมด {self.completed_tasks} จาก {self.total_tasks} รายการ"))

    def _legacy_update_overall_progress(self):
        if self.total_tasks > 0:
            prog = self.completed_tasks / self.total_tasks
            self.progress_bar.set(prog)
            self.status_label_top.configure(text=f"Progress: {self.completed_tasks} / {self.total_tasks} completed")

    def _legacy_single_download_task(self, url, index):
        try:
            out_path = self.settings.get("download_path", os.getcwd())
            ytdlp = get_ytdlp_path()
            cmd = [ytdlp, "--newline", "--no-warnings", "--concurrent-fragments", "5"]
            
            ffmpeg_bin = os.path.dirname(get_ffmpeg_path())
            if os.path.exists(ffmpeg_bin): cmd.extend(["--ffmpeg-location", ffmpeg_bin])
            
            fmt_ui = self.format_combo.get()
            qual_ui = self.quality_combo.get()
            
            if "Audio" in fmt_ui:
                cmd.append("-x")
                ext = "mp3" if "MP3" in fmt_ui else "wav"
                cmd.extend(["--audio-format", ext])
                cmd.extend(["--audio-quality", "0" if "Ultra" in qual_ui else "2"])
            else:
                ext = "mp4" if "MP4" in fmt_ui else "mkv"
                limit = ""
                if "2160p" in qual_ui: limit = "[height<=2160]"
                elif "1440p" in qual_ui: limit = "[height<=1440]"
                elif "1080p" in qual_ui: limit = "[height<=1080]"
                elif "720p" in qual_ui: limit = "[height<=720]"
                
                if ext == "mp4":
                    cmd.extend(["-f", f"bestvideo{limit}[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"])
                    cmd.extend(["--merge-output-format", "mp4"])
                else:
                    cmd.extend(["-f", f"bestvideo{limit}+bestaudio/best"])
                    cmd.extend(["--merge-output-format", "mkv"])

            if self.thumb_only_var.get(): cmd.append("--write-thumbnail")
            
            browser_map = {"Chrome":"chrome", "Edge":"edge", "Firefox":"firefox", "Opera":"opera", "Brave":"brave", "Vivaldi":"vivaldi", "Safari":"safari"}
            browser_ui = self.settings.get("browser_cookie", "None")
            if browser_ui in browser_map: cmd.extend(["--cookies-from-browser", browser_map[browser_ui]])
            
            cmd.extend([
                "-o", f"thumbnail:%(uploader)s/Thumbnails/{index} - %(title)s.%(ext)s",
                "-o", f"%(uploader)s/Videos/{index} - %(title)s.%(ext)s"
            ])
            
            cmd.append(url)
            
            # Ensure output directory exists before starting
            if not os.path.exists(out_path): os.makedirs(out_path, exist_ok=True)
            
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='ignore', cwd=out_path, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
            for line in process.stdout:
                if not self.is_downloading: 
                    process.terminate()
                    break
            process.wait()
            return True
        except: return False

    def _legacy_cancel_download_executor(self):
        self.is_downloading = False
        if self.executor:
            self.executor.shutdown(wait=False, cancel_futures=True)
        self._reset_download_ui()

    def _legacy_reset_download_ui_executor(self):
        self.cancel_btn.pack_forget()
        self.start_btn.pack(side="left", expand=True, fill="x", padx=(0, 10))
        self.progress_bar.set(0)
        self.speed_label.configure(text="Speed: --")
        self.eta_label.configure(text="ETA: --")
        self.size_label.configure(text="Size: --")
        if hasattr(self, 'status_label_top'):
            self.status_label_top.destroy()
            del self.status_label_top

    def _legacy_update_progress(self, line):
        # [download]  45.0% of 10.00MiB at  2.00MiB/s ETA 00:05
        match = re.search(r'\[download\]\s+(\d+\.\d+)%\s+of\s+~?(\d+\.\d+\w+)\s+at\s+(\d+\.\d+\w+/s)\s+ETA\s+(\d+:\d+)', line)
        if match:
            percent = float(match.group(1))
            size, speed, eta = match.group(2), match.group(3), match.group(4)
            self.progress_bar.set(percent / 100)
            self.speed_label.configure(text=f"Speed: {speed}")
            self.eta_label.configure(text=f"ETA: {eta}")
            self.size_label.configure(text=f"Size: {size}")

    def _legacy_cancel_download_process(self):
        if self.download_process:
            self.is_downloading = False
            try: self.download_process.terminate()
            except: pass
        self._reset_download_ui()

    def _legacy_reset_download_ui_process(self):
        self.cancel_btn.pack_forget()
        self.start_btn.pack(side="left", expand=True, fill="x", padx=(0, 10))
        self.progress_bar.set(0)
        self.speed_label.configure(text="Speed: --")
        self.eta_label.configure(text="ETA: --")
        self.size_label.configure(text="Size: --")
        if hasattr(self, 'status_label_top'):
            self.status_label_top.destroy()
            del self.status_label_top

    def start_download(self):
        selected = [v for v in self.fetched_videos if v["var"].get()]
        if not selected:
            messagebox.showwarning("Warning", "Please select at least one video.")
            return

        options = {
            "format": self.format_combo.get(),
            "quality": self.quality_combo.get(),
            "thumb": self.thumb_only_var.get(),
            "browser_cookie": self.settings.get("browser_cookie", "None"),
            "download_path": self.settings.get("download_path", os.getcwd())
        }

        self.is_downloading = True
        self.download_cancelled = False
        self.completed_tasks = 0
        self.failed_tasks = 0
        self.total_tasks = len(selected)
        self.task_progress = {}

        with self.download_lock:
            self.download_processes.clear()

        for item in selected:
            self._set_video_status(item, "Queued", "gray")

        self.start_btn.pack_forget()
        self.cancel_btn.pack(side="left", expand=True, fill="x")
        self.progress_bar.set(0)
        self.speed_label.configure(text="Speed: --")
        self.eta_label.configure(text="ETA: --")
        self.size_label.configure(text="Size: --")

        if hasattr(self, "status_label_top"):
            self.status_label_top.destroy()
        self.status_label_top = ctk.CTkLabel(
            self.progress_frame,
            text=f"Progress: 0 / {self.total_tasks} completed",
            font=ctk.CTkFont(size=13, weight="bold")
        )
        self.status_label_top.pack(side="top", pady=(0, 5))

        logging.info("Starting download batch with %s item(s)", self.total_tasks)
        threading.Thread(target=self._parallel_download_manager, args=(selected, options), daemon=True).start()

    def _parallel_download_manager(self, items, options):
        max_workers_setting = self.settings.get("max_workers", 3)
        worker_count = min(max_workers_setting, max(1, len(items)))
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as executor:
                self.executor = executor
                futures = {
                    executor.submit(self._single_download_task, item, index, options): (item, index)
                    for index, item in enumerate(items)
                }

                for future in concurrent.futures.as_completed(futures):
                    item, index = futures[future]
                    ok = False
                    try:
                        ok = future.result()
                    except Exception:
                        logging.exception("Unhandled download task error")

                    if self.download_cancelled:
                        self.after(0, lambda item=item: self._set_video_status(item, "Cancelled", "orange"))
                        continue

                    if ok:
                        self.completed_tasks += 1
                        self.task_progress[index] = 1.0
                        self.after(0, lambda item=item: self._set_video_status(item, "Done", "green"))
                    else:
                        self.failed_tasks += 1
                        self.task_progress.pop(index, None)
                        self.after(0, lambda item=item: self._set_video_status(item, "Failed", "red"))

                    self.after(0, self._update_overall_progress)
        finally:
            self.is_downloading = False
            self.executor = None
            with self.download_lock:
                self.download_processes.clear()

            self.after(0, self._reset_download_ui)
            self.after(0, self._show_download_summary)

    def _show_download_summary(self):
        if self.download_cancelled:
            messagebox.showinfo(
                "Download stopped",
                f"Stopped by user.\nCompleted: {self.completed_tasks}\nFailed: {self.failed_tasks}\nTotal: {self.total_tasks}"
            )
            return

        if self.failed_tasks:
            messagebox.showwarning(
                "Download finished with errors",
                f"Completed: {self.completed_tasks}\nFailed: {self.failed_tasks}\nLog: {os.path.abspath(LOG_FILE)}"
            )
        else:
            messagebox.showinfo("Download complete", f"Completed all {self.completed_tasks} item(s).")

    def _build_download_command(self, url, index, options, include_cookies=True):
        ytdlp = get_ytdlp_path()
        cmd = [
            ytdlp,
            "--newline",
            "--no-warnings",
            "--continue",
            "--retries", "5",
            "--fragment-retries", "5",
            "--concurrent-fragments", "5",
            "--buffer-size", "1024K",
            "--http-chunk-size", "10M"
        ]

        ffmpeg_bin = os.path.dirname(get_ffmpeg_path())
        if os.path.exists(ffmpeg_bin):
            cmd.extend(["--ffmpeg-location", ffmpeg_bin])

        fmt_ui = options["format"]
        qual_ui = options["quality"]

        if "Audio" in fmt_ui:
            cmd.append("-x")
            ext = "mp3" if "MP3" in fmt_ui else "wav"
            cmd.extend(["--audio-format", ext])
            cmd.extend(["--audio-quality", "0" if "Ultra" in qual_ui else "2"])
            cmd.append("--add-metadata")
            if ext == "mp3":
                cmd.append("--embed-thumbnail")
        else:
            ext = "mp4" if "MP4" in fmt_ui else "mkv"
            limit = ""
            if "2160p" in qual_ui:
                limit = "[height<=2160]"
            elif "1440p" in qual_ui:
                limit = "[height<=1440]"
            elif "1080p" in qual_ui:
                limit = "[height<=1080]"
            elif "720p" in qual_ui:
                limit = "[height<=720]"
            elif "480p" in qual_ui:
                limit = "[height<=480]"
            elif "360p" in qual_ui:
                limit = "[height<=360]"

            if ext == "mp4":
                cmd.extend(["-f", f"bestvideo{limit}[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"])
                cmd.extend(["--merge-output-format", "mp4"])
            else:
                cmd.extend(["-f", f"bestvideo{limit}+bestaudio/best"])
                cmd.extend(["--merge-output-format", "mkv"])

            cmd.extend(["--add-metadata", "--embed-chapters"])

        if options["thumb"]:
            cmd.append("--write-thumbnail")

        browser_ui = options["browser_cookie"]
        if include_cookies:
            cmd.extend(self._browser_cookie_args(browser_ui))

        number = f"{index + 1:03d}"
        cmd.extend([
            "-o", f"thumbnail:%(uploader)s/Thumbnails/{number} - %(title)s.%(ext)s",
            "-o", f"%(uploader)s/Videos/{number} - %(title)s.%(ext)s",
            url
        ])
        return cmd

    def _single_download_task(self, item, index, options):
        url = item["data"].get("webpage_url") or item["data"].get("url")
        if not url:
            self.after(0, lambda: self._set_video_status(item, "Missing URL", "red"))
            return False

        out_path = options["download_path"]
        os.makedirs(out_path, exist_ok=True)
        include_cookies = options.get("browser_cookie") in BROWSER_COOKIE_MAP

        for attempt in range(1, DOWNLOAD_MAX_ATTEMPTS + 1):
            if not self.is_downloading:
                self.after(0, lambda: self._set_video_status(item, "Cancelled", "orange"))
                return False

            if include_cookies:
                attempt_text = f"Downloading (try {attempt}/{DOWNLOAD_MAX_ATTEMPTS})"
            else:
                attempt_text = f"Downloading without browser cookies (try {attempt}/{DOWNLOAD_MAX_ATTEMPTS})"
            self.after(0, lambda text=attempt_text: self._set_video_status(item, text, "orange"))

            cmd = self._build_download_command(url, index, options, include_cookies=include_cookies)
            logging.info("Download task %s attempt %s: %s", index + 1, attempt, " ".join(cmd))
            process = None
            output_lines = []

            try:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="ignore",
                    cwd=out_path,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                )
                with self.download_lock:
                    self.download_processes[index] = process

                for line in process.stdout:
                    if not self.is_downloading:
                        process.terminate()
                        break

                    clean_line = line.strip()
                    if clean_line:
                        output_lines.append(clean_line)
                        if len(output_lines) > 80:
                            output_lines.pop(0)
                        logging.info("[task %s] %s", index + 1, clean_line)
                        self.after(0, lambda idx=index, txt=clean_line: self._update_progress(idx, txt))

                process.wait()

                if not self.is_downloading:
                    self.after(0, lambda: self._set_video_status(item, "Cancelled", "orange"))
                    return False

                if process.returncode == 0:
                    self.task_progress[index] = 1.0
                    self.after(0, self._update_overall_progress)
                    return True

                output_text = "\n".join(output_lines)
                if include_cookies and self._is_cookie_database_error(output_text):
                    include_cookies = False
                    logging.warning(
                        "Browser cookie read failed for task %s; retrying without cookies",
                        index + 1
                    )
                    self.after(
                        0,
                        lambda: self._set_video_status(
                            item,
                            "Cookie issue, retrying without cookies",
                            "orange"
                        )
                    )
                    time.sleep(1)
                    continue

                logging.warning("Download task %s failed with code %s", index + 1, process.returncode)
            except Exception:
                logging.exception("Download task %s crashed", index + 1)
            finally:
                with self.download_lock:
                    self.download_processes.pop(index, None)

            if attempt < DOWNLOAD_MAX_ATTEMPTS and self.is_downloading:
                self.after(0, lambda: self._set_video_status(item, "Retrying...", "orange"))
                time.sleep(2)

        return False

    def _set_video_status(self, item, text, color="gray"):
        label = item.get("status_label")
        if label and label.winfo_exists():
            label.configure(text=text, text_color=color)

    def _update_overall_progress(self):
        if self.total_tasks <= 0:
            return

        active_progress = 0.0
        for index, progress in self.task_progress.items():
            if progress < 1.0:
                active_progress += progress

        overall = min((self.completed_tasks + active_progress) / self.total_tasks, 1.0)
        self.progress_bar.set(overall)

        if hasattr(self, "status_label_top") and self.status_label_top.winfo_exists():
            self.status_label_top.configure(
                text=f"Progress: {self.completed_tasks} / {self.total_tasks} completed | Failed: {self.failed_tasks}"
            )

    def _update_progress(self, index, line):
        progress_match = re.search(
            r"\[download\]\s+(\d+(?:\.\d+)?)%\s+of\s+~?\s*([^\s]+)\s+at\s+([^\s]+)\s+ETA\s+([^\s]+)",
            line
        )
        if progress_match:
            percent = float(progress_match.group(1))
            size = progress_match.group(2)
            speed = progress_match.group(3)
            eta = progress_match.group(4)
            self.task_progress[index] = min(percent / 100, 0.999)
            self.speed_label.configure(text=f"Speed: {speed}")
            self.eta_label.configure(text=f"ETA: {eta}")
            self.size_label.configure(text=f"Size: {size}")
            self._update_overall_progress()
            return

        if "[download] 100%" in line:
            self.task_progress[index] = 1.0
            self._update_overall_progress()
        elif "Destination:" in line:
            self.size_label.configure(text="Preparing file...")
        elif "Merging formats" in line:
            self.eta_label.configure(text="ETA: merging")
        elif "Extracting audio" in line or "Deleting original file" in line:
            self.eta_label.configure(text="ETA: finalizing")

    def cancel_download(self):
        self.download_cancelled = True
        self.is_downloading = False

        with self.download_lock:
            processes = list(self.download_processes.values())

        for process in processes:
            if process and process.poll() is None:
                try:
                    process.terminate()
                except Exception:
                    logging.exception("Failed to terminate download process")

        if self.executor:
            self.executor.shutdown(wait=False, cancel_futures=True)

        self._reset_download_ui()

    def _reset_download_ui(self):
        self.cancel_btn.pack_forget()
        self.start_btn.pack(side="left", expand=True, fill="x", padx=(0, 10))

        if not self.is_downloading:
            self.progress_bar.set(0 if self.download_cancelled else self.progress_bar.get())

        self.speed_label.configure(text="Speed: --")
        self.eta_label.configure(text="ETA: --")
        self.size_label.configure(text="Size: --")

        if hasattr(self, "status_label_top"):
            self.status_label_top.destroy()
            del self.status_label_top

    # --- Converter Logic ---
    def browse_input_file(self):
        f = filedialog.askopenfilename()
        if f:
            self.conv_input_entry.delete(0, "end")
            self.conv_input_entry.insert(0, f)

    def _legacy_convert_media(self):
        src = self.conv_input_entry.get().strip()
        if not src or not os.path.exists(src):
            messagebox.showwarning("Warning", "กรุณาเลือกไฟล์ที่ต้องการแปลง")
            return
        
        self.is_converting = True
        self.convert_btn.pack_forget()
        self.conv_cancel_btn.pack(fill="x", padx=40, pady=(20, 30))
        self.conv_status_label.configure(text="⏳ Converting... 0%", text_color="orange")
        self.conv_progress.set(0)
        
        threading.Thread(target=self._convert_thread, args=(src,), daemon=True).start()

    def _legacy_convert_thread(self, src):
        try:
            target_raw = self.conv_format_combo.get()
            ext = target_raw.split(" ")[0].lower() # mp3, mp4, wav...
            
            out_dir = self.settings.get("download_path", os.getcwd())
            if not os.path.exists(out_dir): os.makedirs(out_dir, exist_ok=True)
            
            base = os.path.splitext(os.path.basename(src))[0]
            out_file = os.path.join(out_dir, f"{base}_converted.{ext}")
            
            ffmpeg = get_ffmpeg_path()
            cmd = [ffmpeg, "-y", "-i", src]
            
            quality = self.conv_quality_combo.get()
            use_gpu = self.gpu_accel_var.get()
            
            if ext in ["mp3", "wav", "aac", "flac"]:
                if "Ultra" in quality: cmd.extend(["-b:a", "320k"])
                elif "Normal" in quality: cmd.extend(["-b:a", "192k"])
                else: cmd.extend(["-b:a", "128k"])
            elif ext == "gif":
                cmd.extend(["-vf", "scale=480:-1:flags=lanczos,fps=10"])
            else: # video
                if use_gpu:
                    # Check for NVENC support
                    has_nvenc = False
                    try:
                        res = subprocess.run([ffmpeg, "-encoders"], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
                        if "h264_nvenc" in res.stdout: has_nvenc = True
                    except: pass
                    
                    if has_nvenc:
                        cmd.extend(["-c:v", "h264_nvenc", "-preset", "p7", "-rc", "vbr", "-cq", "23"])
                    else:
                        # Fallback to CPU
                        if "Ultra" in quality: cmd.extend(["-crf", "18", "-preset", "slow"])
                        elif "Normal" in quality: cmd.extend(["-crf", "23", "-preset", "medium"])
                        else: cmd.extend(["-crf", "28", "-preset", "ultrafast"])
                else:
                    if "Ultra" in quality: cmd.extend(["-crf", "18", "-preset", "slow"])
                    elif "Normal" in quality: cmd.extend(["-crf", "23", "-preset", "medium"])
                    else: cmd.extend(["-crf", "28", "-preset", "ultrafast"])

            cmd.append(out_file)
            
            # Get duration for progress
            duration = 0
            try:
                probe = get_ffprobe_path()
                p_cmd = [probe, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", src]
                res = subprocess.run(p_cmd, capture_output=True, text=True)
                duration = float(res.stdout.strip())
            except: pass

            self.convert_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='ignore', creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
            
            time_pattern = re.compile(r'time=(\d+):(\d+):(\d+\.\d+)')
            for line in self.convert_process.stdout:
                if not self.is_converting: break
                match = time_pattern.search(line)
                if match and duration > 0:
                    h, m, s = match.groups()
                    curr = int(h)*3600 + int(m)*60 + float(s)
                    prog = min(curr/duration, 1.0)
                    self.after(0, lambda p=prog: self.conv_progress.set(p))
                    self.after(0, lambda pct=int(prog*100): self.conv_status_label.configure(text=f"⏳ Converting... {pct}%"))

            self.convert_process.wait()
            
            if self.is_converting:
                if self.convert_process.returncode == 0:
                    self.after(0, lambda: messagebox.showinfo("สำเร็จ", f"แปลงไฟล์สำเร็จแล้ว!\nเก็บไว้ที่: {out_file}"))
                else:
                    self.after(0, lambda: messagebox.showerror("Error", "การแปลงไฟล์ล้มเหลว"))
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Error", str(e)))
        finally:
            self.is_converting = False
            self.after(0, self._reset_conv_ui)
 
    def filter_video_list(self, event=None):
        query = self.search_entry.get().lower()
        for v in self.fetched_videos:
            if query in v["title"]:
                v["frame"].pack(fill="x", padx=5, pady=2)
            else:
                v["frame"].pack_forget()

    def open_link(self, url):
        import webbrowser
        webbrowser.open(url)

    def cancel_conversion(self):
        if self.convert_process:
            self.is_converting = False
            try: self.convert_process.terminate()
            except: pass
        self._reset_conv_ui()

    def _reset_conv_ui(self):
        self.conv_cancel_btn.pack_forget()
        self.convert_btn.pack(fill="x", padx=40, pady=(20, 30))
        self.conv_progress.set(0)
        self.conv_status_label.configure(text="Ready to convert", text_color=("black", "white"))

    def convert_media(self):
        src = self.conv_input_entry.get().strip()
        if not src or not os.path.exists(src):
            messagebox.showwarning("Warning", "Please choose a media file to convert.")
            return

        self.is_converting = True
        self.convert_btn.pack_forget()
        self.conv_cancel_btn.pack(fill="x", padx=40, pady=(20, 30))
        self.conv_status_label.configure(text="Converting... 0%", text_color="orange")
        self.conv_progress.set(0)

        threading.Thread(target=self._convert_thread, args=(src,), daemon=True).start()

    def _convert_thread(self, src):
        try:
            target_raw = self.conv_format_combo.get()
            ext = target_raw.split(" ")[0].lower()

            out_dir = self.settings.get("download_path", os.getcwd())
            os.makedirs(out_dir, exist_ok=True)

            base = os.path.splitext(os.path.basename(src))[0]
            out_file = os.path.join(out_dir, f"{base}_converted.{ext}")
            counter = 2
            while os.path.exists(out_file):
                out_file = os.path.join(out_dir, f"{base}_converted_{counter}.{ext}")
                counter += 1

            ffmpeg = get_ffmpeg_path()
            cmd = [ffmpeg, "-y", "-i", src]

            quality = self.conv_quality_combo.get()
            use_gpu = self.gpu_accel_var.get()

            if ext in ["mp3", "wav", "aac", "flac"]:
                if ext == "mp3":
                    cmd.extend(["-c:a", "libmp3lame"])
                elif ext == "wav":
                    cmd.extend(["-c:a", "pcm_s16le"])
                elif ext == "aac":
                    cmd.extend(["-c:a", "aac"])
                elif ext == "flac":
                    cmd.extend(["-c:a", "flac"])

                if "Ultra" in quality:
                    cmd.extend(["-b:a", "320k"])
                elif "Normal" in quality:
                    cmd.extend(["-b:a", "192k"])
                else:
                    cmd.extend(["-b:a", "128k"])
            elif ext == "gif":
                cmd.extend(["-vf", "scale=480:-1:flags=lanczos,fps=10"])
            else:
                if use_gpu:
                    if self.supported_encoders.get("nvenc"):
                        cmd.extend(["-c:v", "h264_nvenc", "-preset", "p7", "-rc", "vbr", "-cq", "23", "-c:a", "aac"])
                    elif self.supported_encoders.get("qsv"):
                        cmd.extend(["-c:v", "h264_qsv", "-preset", "veryfast", "-global_quality", "23", "-c:a", "aac"])
                    elif self.supported_encoders.get("amf"):
                        cmd.extend(["-c:v", "h264_amf", "-rc", "cqp", "-qp_i", "23", "-qp_p", "23", "-c:a", "aac"])
                    else:
                        # Fallback to CPU
                        cmd.extend(["-c:v", "libx264", "-c:a", "aac"])
                        if "Ultra" in quality:
                            cmd.extend(["-crf", "18", "-preset", "slow"])
                        elif "Normal" in quality:
                            cmd.extend(["-crf", "23", "-preset", "medium"])
                        else:
                            cmd.extend(["-crf", "28", "-preset", "ultrafast"])
                else:
                    cmd.extend(["-c:v", "libx264", "-c:a", "aac"])
                    if "Ultra" in quality:
                        cmd.extend(["-crf", "18", "-preset", "slow"])
                    elif "Normal" in quality:
                        cmd.extend(["-crf", "23", "-preset", "medium"])
                    else:
                        cmd.extend(["-crf", "28", "-preset", "ultrafast"])

            cmd.append(out_file)
            logging.info("Convert command: %s", " ".join(cmd))

            duration = 0
            try:
                probe = get_ffprobe_path()
                p_cmd = [
                    probe,
                    "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    src
                ]
                res = subprocess.run(p_cmd, capture_output=True, text=True, errors="ignore")
                duration = float(res.stdout.strip())
            except Exception:
                logging.exception("Could not read media duration")

            self.convert_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="ignore",
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )

            time_pattern = re.compile(r"time=(\d+):(\d+):(\d+\.\d+)")
            for line in self.convert_process.stdout:
                if not self.is_converting:
                    break

                clean_line = line.strip()
                if clean_line:
                    logging.info("[convert] %s", clean_line)

                match = time_pattern.search(line)
                if match and duration > 0:
                    h, m, s = match.groups()
                    curr = int(h) * 3600 + int(m) * 60 + float(s)
                    prog = min(curr / duration, 1.0)
                    self.after(0, lambda p=prog: self.conv_progress.set(p))
                    self.after(0, lambda pct=int(prog * 100): self.conv_status_label.configure(text=f"Converting... {pct}%"))

            self.convert_process.wait()

            if self.is_converting:
                if self.convert_process.returncode == 0:
                    self.after(0, lambda: messagebox.showinfo("Convert complete", f"Saved to:\n{out_file}"))
                else:
                    self.after(0, lambda: messagebox.showerror("Convert failed", f"FFmpeg failed. Log: {os.path.abspath(LOG_FILE)}"))
        except Exception as e:
            logging.exception("Conversion failed")
            self.after(0, lambda: messagebox.showerror("Error", str(e)))
        finally:
            self.is_converting = False
            self.after(0, self._reset_conv_ui)

    def _legacy_save_settings_from_ui_normalized(self):
        self.settings["download_path"] = self.output_path_entry.get()
        self.settings["browser_cookie"] = self.cookie_combo.get()
        self.settings["theme"] = self.theme_switch_var.get()
        self.save_settings()
        messagebox.showinfo("Settings", "Settings saved.")

    def _legacy_update_frameworks_normalized(self):
        self.update_btn.configure(state="disabled", text="Updating...")
        threading.Thread(target=self._update_thread, daemon=True).start()

    def _legacy_update_thread_normalized(self):
        try:
            ytdlp = get_ytdlp_path()
            if getattr(sys, "frozen", False):
                app_dir = os.path.dirname(sys.executable)
                target = os.path.join(app_dir, "yt-dlp.exe")
                url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
                urllib.request.urlretrieve(url, target)
                self.after(0, lambda: messagebox.showinfo("Update", "yt-dlp updated."))
            else:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-U", "yt-dlp"],
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                )
                self.after(0, lambda: messagebox.showinfo("Update", "yt-dlp package updated."))
        except Exception as e:
            logging.exception("Tool update failed")
            self.after(0, lambda: messagebox.showerror("Update Error", str(e)))
        finally:
            self.after(0, lambda: self.update_btn.configure(state="normal", text="UPDATE TOOLS"))

    # --- Settings Logic ---
    def browse_output_folder(self):
        d = filedialog.askdirectory()
        if d:
            self.output_path_entry.delete(0, "end")
            self.output_path_entry.insert(0, d)

    def open_output_folder(self):
        p = self.output_path_entry.get()
        if not os.path.exists(p): os.makedirs(p, exist_ok=True)
        os.startfile(p)

    def change_theme(self):
        ctk.set_appearance_mode(self.theme_switch_var.get())

    def _legacy_save_settings_from_ui_original(self):
        self.settings["download_path"] = self.output_path_entry.get()
        self.settings["browser_cookie"] = self.cookie_combo.get()
        self.settings["theme"] = self.theme_switch_var.get()
        self.save_settings()
        messagebox.showinfo("Settings", "บันทึกการตั้งค่าเรียบร้อยแล้ว!")

    def auto_paste_link(self):
        try:
            txt = self.clipboard_get().strip()
            if txt.startswith("http"):
                self.url_entry.delete(0, "end")
                self.url_entry.insert(0, txt)
        except: pass

    def _legacy_update_frameworks_original(self):
        self.update_btn.configure(state="disabled", text="⌛ Updating Tool...")
        threading.Thread(target=self._update_thread, daemon=True).start()

    def _legacy_update_thread_original(self):
        try:
            # Simple yt-dlp update
            ytdlp = get_ytdlp_path()
            if getattr(sys, 'frozen', False):
                app_dir = os.path.dirname(sys.executable)
                target = os.path.join(app_dir, "yt-dlp.exe")
                url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
                urllib.request.urlretrieve(url, target)
                self.after(0, lambda: messagebox.showinfo("Update", "yt-dlp อัปเดตสำเร็จ!"))
            else:
                subprocess.run([sys.executable, "-m", "pip", "install", "-U", "yt-dlp"], creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
                self.after(0, lambda: messagebox.showinfo("Update", "Python packages อัปเดตสำเร็จ!"))
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Update Error", str(e)))
        finally:
            self.after(0, lambda: self.update_btn.configure(state="normal", text="🔄 UPDATE TOOLS"))

    def save_settings_from_ui(self):
        self.settings["download_path"] = self.output_path_entry.get()
        self.settings["browser_cookie"] = self.cookie_combo.get()
        self.settings["theme"] = self.theme_switch_var.get()
        try:
            self.settings["max_workers"] = int(self.workers_combo.get())
        except Exception:
            self.settings["max_workers"] = 3
        self.save_settings()
        messagebox.showinfo("Settings", "Settings saved.")

    def update_frameworks(self):
        self.update_btn.configure(state="disabled", text="Updating...")
        threading.Thread(target=self._update_thread, daemon=True).start()

    def _update_thread(self):
        try:
            if getattr(sys, "frozen", False):
                app_dir = os.path.dirname(sys.executable)
                target = os.path.join(app_dir, "yt-dlp.exe")
                url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
                urllib.request.urlretrieve(url, target)
                self.after(0, lambda: messagebox.showinfo("Update", "yt-dlp updated."))
            else:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-U", "yt-dlp"],
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                )
                self.after(0, lambda: messagebox.showinfo("Update", "yt-dlp package updated."))
        except Exception as e:
            logging.exception("Tool update failed")
            self.after(0, lambda: messagebox.showerror("Update Error", str(e)))
        finally:
            self.after(0, lambda: self.update_btn.configure(state="normal", text="UPDATE TOOLS"))

if __name__ == "__main__":
    app = UltimateMediaSuite()
    app.mainloop()
