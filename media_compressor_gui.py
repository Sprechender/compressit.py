import tkinter as tk
from tkinter import filedialog, ttk, messagebox
from media_compressor import MediaCompressor
import threading
from pathlib import Path
import webbrowser
import multiprocessing
from concurrent.futures import ThreadPoolExecutor
import json
import os
import sv_ttk
import darkdetect
import sys
import pywinstyles
from PIL import Image, ImageTk
import io
import base64
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

def get_sv_ttk_path():
    """Get the path to sv_ttk theme files"""
    if getattr(sys, 'frozen', False):
        # If running as compiled executable
        base_path = sys._MEIPASS
    else:
        # If running as script
        base_path = os.path.dirname(sv_ttk.__file__)
    return os.path.join(base_path, 'sv_ttk')

class MediaCompressorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("compressit.py")
        
        # Initialize sv_ttk theme with error handling
        try:
            # Set theme path
            os.environ['SV_TTK_PATH'] = get_sv_ttk_path()
            sv_ttk.set_theme(darkdetect.theme())
        except Exception as e:
            print(f"Warning: Could not set sv_ttk theme: {e}")
            # Fallback to default theme
            self.style = ttk.Style()
            self.style.theme_use('default')
        
        # Increase minimum window size to ensure all elements are visible
        self.root.minsize(600, 800)  # Increased from 500, 600
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        # Main container frame with padding
        self.main_frame = ttk.Frame(self.root, padding="20")
        self.main_frame.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.E, tk.W))
        self.main_frame.columnconfigure(0, weight=1)
        
        # Configure row weights to ensure proper spacing
        for i in range(9):  # Adjust based on total number of rows
            self.main_frame.rowconfigure(i, weight=0)  # Set all rows to not expand
        self.main_frame.rowconfigure(7, weight=1)  # Make results frame expandable
        
        # Apply Sun Valley theme
        sv_ttk.set_theme(darkdetect.theme())  # Automatically use system theme
        
        # Apply theme to title bar on Windows
        if sys.platform == "win32":
            self.apply_theme_to_titlebar()
        
        # Configure style
        self.style = ttk.Style()
        self.style.configure('TButton', padding=6)
        self.style.configure('Header.TLabel', font=('Helvetica', 24, 'bold'))
        self.style.configure('Subheader.TLabel', font=('Helvetica', 12))
        self.style.configure('Link.TLabel', foreground='blue', cursor='hand2')
        
        # Initialize StringVars
        self.status_var = tk.StringVar(value="Select a directory to begin")
        self.quality_var = tk.StringVar(value="80")
        self.thread_var = tk.StringVar(value=str(multiprocessing.cpu_count()))
        self.file_count = tk.StringVar(value="Files: 0/0")
        
        # Add these lines to initialize the checkbox variables
        self.process_images_var = tk.BooleanVar(value=True)
        self.process_videos_var = tk.BooleanVar(value=True)
        self.hw_var = tk.BooleanVar(value=True)
        self.codec_var = tk.StringVar(value="h265")
        
        # Add replace files checkbox
        self.replace_files_var = tk.BooleanVar(value=False)
        
        self.compressor = MediaCompressor()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.compression_in_progress = False
        
        self.settings_file = Path.home() / '.compressit_settings.json'
        self.load_settings()
        
        # GitHub icon in base64 (black version)
        self.github_icon_base64 = """
        iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAAGXRFWHRTb2Z0d2FyZQBBZG9iZSBJbWFnZVJlYWR5ccllPAAAAyRpVFh0WE1MOmNvbS5hZG9iZS54bXAAAAAAADw/eHBhY2tldCBiZWdpbj0i77u/IiBpZD0iVzVNME1wQ2VoaUh6cmVTek5UY3prYzlkIj8+IDx4OnhtcG1ldGEgeG1sbnM6eD0iYWRvYmU6bnM6bWV0YS8iIHg6eG1wdGs9IkFkb2JlIFhNUCBDb3JlIDUuMy1jMDExIDY2LjE0NTY2MSwgMjAxMi8wMi8wNi0xNDo1NjoyNyAgICAgICAgIj4gPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4gPHJkZjpEZXNjcmlwdGlvbiByZGY6YWJvdXQ9IiIgeG1sbnM6eG1wPSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvIiB4bWxuczp4bXBNTT0iaHR0cDovL25zLmFkb2JlLmNvbS94YXAvMS4wL21tLyIgeG1sbnM6c3RSZWY9Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC9zVHlwZS9SZXNvdXJjZVJlZiMiIHhtcDpDcmVhdG9yVG9vbD0iQWRvYmUgUGhvdG9zaG9wIENTNiAoTWFjaW50b3NoKSIgeG1wTU06SW5zdGFuY2VJRD0ieG1wLmlpZDpFNTE3OEEyQTk5QTAxMUUyOUExNUJDMTA0NkE4OTA0RCIgeG1wTU06RG9jdW1lbnRJRD0ieG1wLmRpZDpFNTE3OEEyQjk5QTAxMUUyOUExNUJDMTA0NkE4OTA0RCI+IDx4bXBNTTpEZXJpdmVkRnJvbSBzdFJlZjppbnN0YW5jZUlEPSJ4bXAuaWlkOkU1MTc4QTI4OTlBMDExRTI5QTE1QkMxMDQ2QTg5MDREIiBzdFJlZjpkb2N1bWVudElEPSJ4bXAuZGlkOkU1MTc4QTI5OTlBMDExRTI5QTE1QkMxMDQ2QTg5MDREIi8+IDwvcmRmOkRlc2NyaXB0aW9uPiA8L3JkZjpSREY+IDwveDp4bXBtZXRhPiA8P3hwYWNrZXQgZW5kPSJyIj8+m4QGuQAAAyRJREFUeNrEl21ojWEYx895TDPbMNlBK46IUiNmPvHBSUjaqc0H8pF5+aDUKPEBqU2NhRQpX5Rv5jWlDIWlMCv7MMSWsWwmb3tpXub4XXWdPHvc9/Gc41nu+nedc7/8r/99PffLdYdDPsvkwsgkTBwsA/PADJCnzX2gHTwBt8Hl7p537/3whn04XoDZDcpBlk+9P8AFcAghzRkJwPF4zGGw0Y9QS0mAM2AnQj77FqCzrtcwB1Hk81SYojHK4DyGuQ6mhIIrBWB9Xm7ug/6B/nZrBHBegrkFxoVGpnwBMSLR9EcEcC4qb8pP14BWcBcUgewMnF3T34VqhWMFkThLJAalwnENOAKiHpJq1FZgI2AT6HZtuxZwR9GidSHtI30jOrbawxlVX78/AbNfhHlomEUJJI89O2MqeE79T8/nk8nMBm/dK576hZgmA3cp/R4l9/UeSxiHLVIlNm4nFfT0bxyuIj7LHRTKai+zdJobwMKzcZSJb0ePV5PKN+BqAAKE47UlMnERELMM3EdYP/yrd+XYb2mOiYBiQ8OQnoRBlXrl9JZix7D1pHTazu4MoyBcnYamqAjIMTR8G4FT8LuhLsexXYYjICBiqhQBvYb6fLZIJCjPypVvaOoVAW2WcasCnL2Nq82xHJNSqlCeFcDshaPK0twkAhosjZL31QYw+1rlMpWGMArl23SBsZZO58F2tlJXmjOXS+s4WGvpMiBJT/I2PInZ6lIs9/hBsNS1hS6BG0DSqmYEDRlCXQrmy50P1oDRKTSegmNbUsA0zDMwRhPJXeCE3vWLPQMvan6X8AgIa1vcR4AkGZkDR4ejJ1UHpsaVI0g2LInpOsNFUud1rhxSV+fzC9Woz2EZkWQuja7/B+jUrgtIMpy9YCW4n4K41YfzRneW5E1KJTe4B2Zq1Q5EHEtj4U3AfEzR5SVY4l7QYQPJdN2as7RKBF0BPZqqH4VgMAMBL8Byxr7y8zCZiDlnOcEKIPmUpgB5Z2ww5RdOiiRiNajUmWda5IG6WbhsyY2fx6m8gLcoJDJFkH219M3We1+cnda93pfycZpIJEL/s/wSYADmOAwAQgdpBAAAAABJRU5ErkJggg==
        """
        
        # Configure additional styles for results
        self.style.configure('Results.TFrame', padding=20)
        self.style.configure('Accent.TButton', 
                            background='#0078D4',
                            foreground='white')
        
        # Create a custom font for results
        self.results_font = ('Consolas', 10)
        
        # Update results frame configuration
        self.results_frame = ttk.Frame(self.main_frame, style='Results.TFrame')
        self.results_frame.grid(row=7, column=0, sticky=(tk.W, tk.E), pady=20)
        self.results_frame.grid_remove()  # Hide initially
        
        # Configure results label with better styling
        self.results_label = ttk.Label(
            self.results_frame,
            justify=tk.LEFT,
            font=self.results_font,
            wraplength=400
        )
        self.results_label.pack(pady=10)

        self.create_widgets()

        # Add notification tracking
        self.active_notifications = []
        self.notification_padding = 10  # Space between notifications

    def create_widgets(self):
        # Header section with more padding
        self.header_frame = ttk.Frame(self.main_frame)
        self.header_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 30))
        
        ttk.Label(self.header_frame, text="compressit.py", style='Header.TLabel').pack(pady=(10, 5))
        ttk.Label(self.header_frame, text="Compress your media files easily", style='Subheader.TLabel').pack(pady=(0, 10))

        # Directory frame with better spacing
        self.dir_frame = ttk.Frame(self.main_frame)
        self.dir_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 20))
        
        ttk.Label(self.dir_frame, textvariable=self.status_var).pack(side=tk.LEFT, padx=10, pady=10)
        ttk.Button(self.dir_frame, text="Select Directory", command=self.select_directory).pack(side=tk.RIGHT, padx=10, pady=10)

        # Settings frame with improved layout
        self.settings_frame = ttk.Frame(self.main_frame)
        self.settings_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 20))
        
        settings_label_frame = ttk.LabelFrame(self.settings_frame, text="Settings", padding=(10, 5))
        settings_label_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Quality setting with more space
        quality_frame = ttk.Frame(settings_label_frame)
        quality_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(quality_frame, text="Quality (1-100):").pack(side=tk.LEFT)
        ttk.Entry(quality_frame, textvariable=self.quality_var, width=5).pack(side=tk.LEFT, padx=(10, 0))
        
        # Thread setting with more space
        thread_frame = ttk.Frame(settings_label_frame)
        thread_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(thread_frame, text="Threads:").pack(side=tk.LEFT)
        ttk.Entry(thread_frame, textvariable=self.thread_var, width=5).pack(side=tk.LEFT, padx=(10, 0))

        # Filetype frame with better spacing
        self.filetype_frame = ttk.Frame(self.main_frame)
        self.filetype_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 20))
        
        filetype_label_frame = ttk.LabelFrame(self.filetype_frame, text="File Types", padding=(10, 5))
        filetype_label_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Checkbutton(filetype_label_frame, text="Process Images", variable=self.process_images_var).pack(side=tk.LEFT, padx=20, pady=10)
        ttk.Checkbutton(filetype_label_frame, text="Process Videos", variable=self.process_videos_var).pack(side=tk.LEFT, padx=20, pady=10)

        # Codec frame with improved spacing
        self.codec_frame = ttk.Frame(self.main_frame)
        self.codec_frame.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=(0, 20))
        
        codec_label_frame = ttk.LabelFrame(self.codec_frame, text="Codec Settings", padding=(10, 5))
        codec_label_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Checkbutton(codec_label_frame, text="Use Hardware Acceleration", variable=self.hw_var).pack(side=tk.LEFT, padx=20, pady=10)
        ttk.Radiobutton(codec_label_frame, text="H.265", variable=self.codec_var, value="h265").pack(side=tk.LEFT, padx=20, pady=10)
        ttk.Radiobutton(codec_label_frame, text="H.264", variable=self.codec_var, value="h264").pack(side=tk.LEFT, padx=20, pady=10)

        # Add replace files option after codec frame
        self.replace_frame = ttk.Frame(self.main_frame)
        self.replace_frame.grid(row=5, column=0, sticky=(tk.W, tk.E), pady=(0, 20))
        
        replace_label_frame = ttk.LabelFrame(self.replace_frame, text="File Handling", padding=(10, 5))
        replace_label_frame.pack(fill=tk.X, padx=10, pady=5)
        
        replace_option_frame = ttk.Frame(replace_label_frame)
        replace_option_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Add replace files checkbox with warning
        ttk.Checkbutton(
            replace_option_frame, 
            text="Replace original files", 
            variable=self.replace_files_var
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        # Add warning label
        warning_label = ttk.Label(
            replace_option_frame,
            text="⚠️ Original files will be backed up to .compressit_backup",
            foreground='orange'
        )
        warning_label.pack(side=tk.LEFT)

        # Progress frame with better layout and minimum size
        self.progress_frame = ttk.Frame(self.main_frame)
        self.progress_frame.grid(row=6, column=0, sticky=(tk.W, tk.E), pady=(0, 20))
        
        self.progress = ttk.Progressbar(self.progress_frame, length=300, mode='determinate')
        self.progress.pack(fill=tk.X, padx=10, pady=(10, 5))
        
        # File count label with better visibility
        file_count_label = ttk.Label(self.progress_frame, textvariable=self.file_count)
        file_count_label.pack(fill=tk.X, padx=10, pady=(0, 10))

        # Create buttons frame
        self.buttons_frame = ttk.Frame(self.main_frame)
        self.buttons_frame.grid(row=7, column=0, pady=10, sticky=(tk.W, tk.E))
        
        # Create start button
        self.start_button = ttk.Button(
            self.buttons_frame,
            text="Start Compression",
            command=self.start_compression,
            style='Accent.TButton'
        )
        self.start_button.grid(row=0, column=0, padx=5)
        
        # Create cancel button (hidden initially)
        self.cancel_button = ttk.Button(
            self.buttons_frame,
            text="Cancel",
            command=self.cancel_compression
        )
        self.cancel_button.grid(row=0, column=1, padx=5)
        self.cancel_button.grid_remove()  # Hide initially

        # Results frame with improved layout
        self.results_frame = ttk.Frame(self.main_frame)
        self.results_frame.grid(row=8, column=0, sticky=(tk.N, tk.S, tk.E, tk.W), pady=(0, 20))
        
        results_container = ttk.Frame(self.results_frame)
        results_container.pack(expand=True, fill=tk.BOTH)
        
        self.results_label = ttk.Label(results_container, text="", justify=tk.LEFT)
        self.results_label.pack(pady=10)
        self.results_frame.grid_remove()

        # GitHub frame with improved positioning
        self.github_frame = ttk.Frame(self.main_frame)
        self.github_frame.grid(row=9, column=0, sticky=(tk.S, tk.E, tk.W), pady=(0, 10))
        
        # Center the GitHub icon
        github_container = ttk.Frame(self.github_frame)
        github_container.pack(expand=True)
        
        # Create GitHub icon with theme-appropriate color
        github_icon_data = base64.b64decode(self.github_icon_base64)
        github_image = Image.open(io.BytesIO(github_icon_data))
        
        # Convert to RGBA if not already
        if github_image.mode != 'RGBA':
            github_image = github_image.convert('RGBA')
        
        # Create two versions of the icon (normal and hover)
        is_dark = sv_ttk.get_theme() == "dark"
        
        # Function to tint image
        def tint_image(image, color):
            image = image.copy()
            alpha = image.split()[3]
            image = image.convert('RGB')
            image = Image.new('RGB', image.size, color)
            image.putalpha(alpha)
            return image
        
        # Create normal and hover versions
        normal_color = "#FFFFFF" if is_dark else "#000000"
        hover_color = "#CCCCCC" if is_dark else "#666666"
        
        normal_image = tint_image(github_image, normal_color)
        hover_image = tint_image(github_image, hover_color)
        
        # Resize both images
        normal_image = normal_image.resize((24, 24), Image.Resampling.LANCZOS)
        hover_image = hover_image.resize((24, 24), Image.Resampling.LANCZOS)
        
        # Store both versions
        self.github_photo = ImageTk.PhotoImage(normal_image)
        self.github_photo_hover = ImageTk.PhotoImage(hover_image)
        
        # Create the label
        self.github_button = ttk.Label(github_container, image=self.github_photo, cursor='hand2')
        self.github_button.pack(pady=10)
        
        # Bind hover events
        self.github_button.bind('<Enter>', lambda e: self.github_button.configure(image=self.github_photo_hover))
        self.github_button.bind('<Leave>', lambda e: self.github_button.configure(image=self.github_photo))
        self.github_button.bind('<Button-1>', self.open_github)

        # Configure frame weights
        for frame in [self.dir_frame, self.settings_frame, self.filetype_frame, 
                     self.codec_frame, self.progress_frame, self.buttons_frame, 
                     self.results_frame, self.github_frame]:
            frame.columnconfigure(0, weight=1)

    def select_directory(self):
        self.directory = filedialog.askdirectory()
        if self.directory:
            self.status_var.set(f"Selected: {self.directory}")
            # Show directory selection notification
            self.show_notification(
                "Directory Selected",
                f"Selected directory: {self.directory}"
            )

    def start_compression(self):
        """Start the compression process"""
        try:
            if not hasattr(self, 'directory'):
                messagebox.showerror("Error", "Please select a directory first")
                return

            # Reset progress
            self.progress['value'] = 0
            self.file_count.set("Files: 0/0")
            self.compression_results = {
                'original_size': 0,
                'compressed_size': 0,
                'successful': 0,
                'total_files': 0,
                'skipped': 0,
                'ratio': 0
            }
            
            # Show notification
            self.show_notification(
                "Compression Started",
                f"Starting compression of files in {self.directory}"
            )
            
            # Disable start button and show cancel button
            self.start_button.grid_remove()
            self.cancel_button.grid()
            self.compression_in_progress = True
            
            # Get settings
            try:
                quality = int(self.quality_var.get())
                thread_count = int(self.thread_var.get())
            except ValueError:
                messagebox.showerror("Error", "Quality and thread count must be numbers")
                return
            
            # Start compression in a separate thread
            self.compression_thread = threading.Thread(
                target=self.run_compression,
                args=(quality, thread_count)
            )
            self.compression_thread.start()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start compression: {str(e)}")
            self.compression_complete()

    def run_compression(self, quality, thread_count):
        """Run the compression process"""
        try:
            # Create compressor instance
            self.compressor = MediaCompressor()
            
            # Get list of media files first
            media_files = self.get_media_files()
            if not media_files:
                self.status_var.set("No files to process")
                self.compression_complete()
                return
            
            # Create output directory
            output_dir = Path(self.directory) / 'compressed'
            output_dir.mkdir(exist_ok=True)
            
            # Run compression with correct arguments
            stats = self.compressor.compress_directory(
                media_files=media_files,
                output_dir=output_dir,
                quality=quality,
                thread_count=thread_count,
                progress_callback=self.update_progress,
                use_hardware=self.hw_var.get(),
                codec=self.codec_var.get(),
                replace_files=self.replace_files_var.get(),
                cancel_check=lambda: not self.compression_in_progress
            )
            
            # Store results
            self.compression_results = stats
            
            # Update UI in main thread
            self.root.after(0, self.compression_complete)
            
        except Exception as e:
            print(f"Compression error: {str(e)}")
            self.root.after(0, lambda: messagebox.showerror("Error", f"Compression failed: {str(e)}"))
            self.root.after(0, self.compression_complete)

    def update_progress(self, progress_info):
        """Update the progress bar and file count"""
        if isinstance(progress_info, dict):
            # Update progress bar if progress info exists
            if 'progress' in progress_info:
                self.progress['value'] = progress_info['progress']
                
                # Update file count
                self.file_count.set(
                    f"Files: {progress_info['files_processed']}/{progress_info['total_files']}"
                )
            
            # Check for skipped files
            if progress_info.get('skipped'):
                self.show_notification(
                    "File Skipped",
                    f"Skipped: {progress_info['current_file']} ({progress_info.get('reason', 'unknown reason')})"
                )
            
            # Update status for current file
            if 'current_file' in progress_info:
                current_file = progress_info['current_file']
                self.status_var.set(f"Processing: {current_file}")
        
        elif isinstance(progress_info, str):
            if progress_info == 'error':
                self.show_notification(
                    "Error",
                    "An error occurred during compression"
                )

    def cancel_compression(self):
        """Cancel the compression process"""
        if self.compression_in_progress:
            self.is_cancelled = True
            self.status_var.set("Cancelling compression...")
            self.cancel_button.configure(state='disabled')
            self.show_notification(
                "Cancelling",
                "Stopping compression process..."
            )

    def compression_complete(self):
        """Handle completion of compression process"""
        self.compression_in_progress = False
        
        # Update button visibility
        if hasattr(self, 'cancel_button'):
            self.cancel_button.grid_remove()
        if hasattr(self, 'start_button'):
            self.start_button.grid()
        
        if not hasattr(self, 'compression_results'):
            self.status_var.set("No compression results available")
            return

        # Calculate results
        space_saved = self.compression_results['original_size'] - self.compression_results['compressed_size']
        space_saved_mb = space_saved / (1024 * 1024)
        
        # Show completion notification
        self.show_notification(
            "Compression Complete",
            f"Successfully compressed {self.compression_results['successful']} files\n"
            f"Space saved: {space_saved_mb:.1f} MB"
        )
        
        # Show the summary window
        CompressionSummaryWindow(self, self.compression_results)
        
        # Update status
        self.status_var.set("Compression complete! Switch to the summary window for details.")
        self.progress['value'] = 100

    def open_github(self, event):
        webbrowser.open("https://github.com/Sprechender/compressit.py")

    def on_closing(self):
        if self.compression_in_progress:
            if messagebox.askokcancel("Quit", "Compression is in progress. Do you want to cancel and quit?"):
                self.is_cancelled = True
                self.root.after(100, self.check_and_close)  # Check periodically if it's safe to close
        else:
            self.root.destroy()

    def check_and_close(self):
        if not self.compression_in_progress:
            self.root.destroy()
        else:
            self.root.after(100, self.check_and_close)  # Check again after 100ms

    def load_settings(self):
        try:
            if self.settings_file.exists():
                with open(self.settings_file) as f:
                    settings = json.load(f)
                    self.quality_var.set(settings.get('quality', 80))
                    self.thread_var.set(settings.get('threads', multiprocessing.cpu_count()))
                    self.hw_var.set(settings.get('hw_acceleration', True))
                    self.codec_var.set(settings.get('codec', 'h264'))
        except Exception as e:
            print(f"Error loading settings: {e}")

    def save_settings(self):
        try:
            settings = {
                'quality': int(self.quality_var.get()),
                'threads': int(self.thread_var.get()),
                'hw_acceleration': self.hw_var.get(),
                'codec': self.codec_var.get()
            }
            with open(self.settings_file, 'w') as f:
                json.dump(settings, f)
            messagebox.showinfo("Success", "Settings saved successfully")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save settings: {e}")

    def apply_theme_to_titlebar(self):
        version = sys.getwindowsversion()

        if version.major == 10 and version.build >= 22000:
            # Windows 11
            pywinstyles.change_header_color(self.root, 
                "#1c1c1c" if sv_ttk.get_theme() == "dark" else "#fafafa")
        elif version.major == 10:
            # Windows 10
            pywinstyles.apply_style(self.root, 
                "dark" if sv_ttk.get_theme() == "dark" else "normal")
            
            # Update title bar color
            self.root.wm_attributes("-alpha", 0.99)
            self.root.wm_attributes("-alpha", 1)

    def show_notification(self, title, message):
        """Show a temporary notification window"""
        try:
            # Calculate position based on existing notifications
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            notification_height = 100
            
            # Calculate base position (bottom right)
            x = screen_width - 420
            y = screen_height - 140
            
            # Adjust y position based on active notifications
            total_height = (notification_height + self.notification_padding) * len(self.active_notifications)
            y -= total_height
            
            # Create notification window
            notification = tk.Toplevel()
            notification.withdraw()  # Hide initially to prevent flickering
            
            # Remove window decorations and set attributes
            notification.overrideredirect(True)
            notification.attributes('-topmost', True)
            
            # Configure window
            notification.geometry(f"400x{notification_height}+{x}+{y}")
            
            # Create main frame with rounded corners and shadow effect
            main_frame = ttk.Frame(notification, style='Notification.TFrame')
            main_frame.pack(fill="both", expand=True)
            
            # Configure notification styles
            self.style.configure('Notification.TFrame', background='#2c2c2c')
            self.style.configure('NotificationTitle.TLabel', 
                               font=('Helvetica', 11, 'bold'),
                               foreground='white',
                               background='#2c2c2c')
            self.style.configure('NotificationMessage.TLabel',
                               font=('Helvetica', 10),
                               foreground='#e0e0e0',
                               background='#2c2c2c')
            
            # Add title and message
            ttk.Label(
                main_frame,
                text=title,
                style='NotificationTitle.TLabel'
            ).pack(anchor="w", padx=15, pady=(15, 5))
            
            ttk.Label(
                main_frame,
                text=message,
                style='NotificationMessage.TLabel',
                wraplength=370  # Prevent text from extending beyond window
            ).pack(anchor="w", padx=15, pady=(0, 15))
            
            # Keep track of this notification
            self.active_notifications.append(notification)
            
            # Make window visible with fade-in effect
            notification.deiconify()
            notification.attributes('-alpha', 0.0)
            
            def fade_in():
                alpha = notification.attributes('-alpha')
                if alpha < 0.9:
                    notification.attributes('-alpha', alpha + 0.1)
                    notification.after(20, fade_in)
            
            fade_in()
            
            def remove_notification():
                if notification in self.active_notifications:
                    self.active_notifications.remove(notification)
                    notification.destroy()
                    self.reposition_notifications()
            
            # Add hover effect
            def on_enter(e):
                notification.attributes('-alpha', 1.0)
            
            def on_leave(e):
                notification.attributes('-alpha', 0.9)
            
            notification.bind('<Enter>', on_enter)
            notification.bind('<Leave>', on_leave)
            notification.bind('<Button-1>', lambda e: remove_notification())
            
            # Smooth fade-out
            def fade_out():
                alpha = notification.attributes('-alpha')
                if alpha > 0:
                    notification.attributes('-alpha', alpha - 0.1)
                    notification.after(20, fade_out)
                else:
                    remove_notification()
            
            # Auto-close timer
            notification.after(2500, fade_out)
        except Exception as e:
            print(f"Error showing notification: {e}")
            # Fallback to console output if notification fails
            print(f"{title}: {message}")

    def reposition_notifications(self):
        """Reposition all active notifications to stack properly"""
        try:
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            notification_height = 100
            
            for i, notification in enumerate(reversed(self.active_notifications)):
                x = screen_width - 420
                y = screen_height - 140 - (i * (notification_height + self.notification_padding))
                notification.geometry(f"400x{notification_height}+{x}+{y}")
        except Exception as e:
            print(f"Error repositioning notifications: {e}")

    def get_media_files(self):
        """Get all media files from the selected directory"""
        if not hasattr(self, 'directory') or not self.directory:
            return []
        
        media_files = []
        supported_formats = {
            'images': ['.jpg', '.jpeg', '.png', '.webp'],
            'videos': ['.mp4', '.mov', '.avi', '.mkv', '.webm']
        }
        
        try:
            for root, _, files in os.walk(self.directory):
                for file in files:
                    file_path = Path(root) / file
                    extension = file_path.suffix.lower()
                    
                    # Check if file should be processed based on user preferences
                    is_image = extension in supported_formats['images']
                    is_video = extension in supported_formats['videos']
                    
                    if ((is_image and self.process_images_var.get()) or 
                        (is_video and self.process_videos_var.get())):
                        media_files.append(file_path)
            
            # Sort files for consistent processing order
            media_files.sort()
            return media_files
            
        except Exception as e:
            print(f"Error scanning directory: {e}")
            self.status_var.set(f"Error scanning directory: {e}")
            return []

class CompressionSummaryWindow:
    def __init__(self, parent, compression_results):
        self.parent = parent  # MediaCompressorGUI instance
        self.window = tk.Toplevel(parent.root)
        self.compression_results = compression_results
        
        self.window.title("Compression Summary")
        self.window.geometry("500x600")
        self.window.minsize(500, 600)
        
        # Configure style
        self.style = ttk.Style()
        self.style.configure('Stat.TLabel', 
                           font=('Helvetica', 24, 'bold'),
                           foreground='#0078D4')
        self.style.configure('StatLabel.TLabel',
                           font=('Helvetica', 10))
        
        # Create main frame
        main_frame = ttk.Frame(self.window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Add stats and create UI
        self.create_summary_ui(main_frame)

    def create_summary_ui(self, main_frame):
        # Title
        ttk.Label(main_frame, text="Compression Summary", 
                 font=('Helvetica', 24, 'bold')).pack(pady=(0, 20))
        
        # Stats container
        stats_frame = ttk.Frame(main_frame)
        stats_frame.pack(fill=tk.X, pady=10)
        stats_frame.columnconfigure(0, weight=1)
        stats_frame.columnconfigure(1, weight=1)
        
        # Files processed
        self.create_stat_pair(
            stats_frame, 0,
            str(self.compression_results['successful']),
            "Files Compressed"
        )
        
        self.create_stat_pair(
            stats_frame, 1,
            str(self.compression_results['skipped']),
            "Files Skipped"
        )
        
        # Size stats
        original_size_mb = self.compression_results['original_size'] / (1024 * 1024)
        compressed_size_mb = self.compression_results['compressed_size'] / (1024 * 1024)
        space_saved_mb = original_size_mb - compressed_size_mb
        compression_ratio = self.compression_results['ratio']
        
        self.create_stat_pair(
            stats_frame, 2,
            f"{original_size_mb:.1f} MB",
            "Original Size"
        )
        
        self.create_stat_pair(
            stats_frame, 3,
            f"{compressed_size_mb:.1f} MB",
            "Compressed Size"
        )
        
        self.create_stat_pair(
            stats_frame, 4,
            f"{space_saved_mb:.1f} MB",
            "Space Saved"
        )
        
        self.create_stat_pair(
            stats_frame, 5,
            f"{compression_ratio:.1f}%",
            "Compression Ratio"
        )
        
        # Close button
        ttk.Button(
            main_frame,
            text="Close",
            command=self.window.destroy
        ).pack(pady=20)

    def create_stat_pair(self, parent, row, value, label):
        """Helper method to create a stat value and label pair"""
        # Container for the pair
        frame = ttk.Frame(parent)
        frame.grid(row=row // 2, column=row % 2, padx=10, pady=10, sticky='nsew')
        
        # Value (large number)
        ttk.Label(
            frame,
            text=value,
            style='Stat.TLabel'
        ).pack(anchor='center')
        
        # Label (description)
        ttk.Label(
            frame,
            text=label,
            style='StatLabel.TLabel'
        ).pack(anchor='center')

if __name__ == "__main__":
    root = tk.Tk()
    app = MediaCompressorGUI(root)
    root.mainloop() 