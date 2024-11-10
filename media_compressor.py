from pathlib import Path
from PIL import Image
import pillow_heif
from typing import List, Dict
import os
import subprocess
import shutil
from moviepy.editor import VideoFileClip
from PIL import ImageOps
from concurrent.futures import ThreadPoolExecutor
import multiprocessing
import threading
import ffmpeg
import concurrent.futures
from functools import lru_cache
import tkinter as tk
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox
import tkinter.ttk as ttk
import json
from tkinterdnd2 import *

class MediaCompressor:
    def __init__(self):
        self.supported_image_formats = {'.jpg', '.jpeg', '.png', '.webp', '.heic'}
        self.supported_video_formats = {'.mov', '.mp4', '.avi', '.mkv', '.wmv', '.flv'}
        self.supported_formats = self.supported_image_formats.union(self.supported_video_formats)
        self.hw_encoders = self._detect_hw_encoders()
        # Register HEIF opener for .heic files
        pillow_heif.register_heif_opener()
        self.compression_stats = {
            'original_size': 0,
            'compressed_size': 0,
            'files_processed': 0,
            'files_skipped': 0
        }

    def _detect_hw_encoders(self) -> Dict[str, str]:
        """Detect available hardware encoders"""
        encoders = {}
        
        # Check for NVIDIA NVENC
        if shutil.which('ffmpeg'):
            try:
                result = subprocess.run(['ffmpeg', '-encoders'], capture_output=True, text=True)
                if 'hevc_nvenc' in result.stdout:
                    encoders['nvidia'] = 'hevc_nvenc'
                if 'h264_nvenc' in result.stdout:
                    encoders['nvidia_h264'] = 'h264_nvenc'
                if 'hevc_qsv' in result.stdout:
                    encoders['intel'] = 'hevc_qsv'
                if 'hevc_videotoolbox' in result.stdout:
                    encoders['mac'] = 'hevc_videotoolbox'
                if 'hevc_amf' in result.stdout:
                    encoders['amd'] = 'hevc_amf'
            except Exception:
                pass
        return encoders

    def find_media(self, root_dir: str) -> List[Path]:
        """Find all supported media files in directory and subdirectories."""
        root_path = Path(root_dir)
        media_files = []
        
        for path in root_path.rglob('*'):
            if path.suffix.lower() in self.supported_formats:
                media_files.append(path)
        
        return media_files

    def compress_image(self, input_path, output_path=None, quality=85, progress_callback=None):
        """Compress a single image file."""
        try:
            input_path = Path(input_path)
            
            # Create default output path if none provided
            if output_path is None:
                output_dir = input_path.parent / 'compressed'
                output_dir.mkdir(exist_ok=True)
                output_path = output_dir / input_path.name
            else:
                output_path = Path(output_path)

            # Open the image and get EXIF
            with Image.open(input_path) as img:
                # Get original EXIF data
                try:
                    exif_dict = img.getexif()
                    if exif_dict is None:
                        exif_dict = {}
                except Exception:
                    exif_dict = {}
                
                # Preserve orientation
                orientation = exif_dict.get(274)  # 274 is the orientation tag
                if orientation:
                    rotations = {
                        3: Image.Transpose.ROTATE_180,
                        6: Image.Transpose.ROTATE_270,
                        8: Image.Transpose.ROTATE_90
                    }
                    if orientation in rotations:
                        img = img.transpose(rotations[orientation])
                        exif_dict[274] = 1
                
                # Get original file size
                original_size = input_path.stat().st_size
                self.compression_stats['original_size'] += original_size
                
                # Save with EXIF data
                if input_path.suffix.lower() == '.heic':
                    output_path = output_path.with_suffix('.jpg')
                
                img.save(output_path, quality=quality, optimize=True, exif=exif_dict)
                
                # Check compression ratio
                compressed_size = output_path.stat().st_size
                compression_ratio = compressed_size / original_size
                
                # If JPEG compression isn't effective, try HEIC
                if compression_ratio > 0.95 and input_path.suffix.lower() in {'.jpg', '.jpeg', '.png'}:
                    heic_path = output_path.with_suffix('.heic')
                    try:
                        img.save(heic_path, format='HEIF', quality=quality)
                        
                        if heic_path.stat().st_size < compressed_size:
                            compressed_size = heic_path.stat().st_size
                            output_path.unlink()
                            output_path = heic_path
                        else:
                            heic_path.unlink()
                    except Exception as heic_error:
                        print(f"HEIC conversion failed: {str(heic_error)}")
                        if heic_path.exists():
                            heic_path.unlink()
                
                # If compression wasn't effective at all, skip the file
                if compression_ratio > 0.95:
                    output_path.unlink()
                    print(f"Skipped {input_path.name} (already optimized)")
                    self.compression_stats['files_skipped'] += 1
                    if progress_callback:
                        progress_callback({
                            'skipped': True,
                            'current_file': input_path.name,
                            'reason': 'already optimized'
                        })
                    return False
                    
                print(f"Compressed image: {input_path.name} (ratio: {compression_ratio:.2f})")
                self.compression_stats['compressed_size'] += compressed_size
                self.compression_stats['files_processed'] += 1
                return True
                
        except Exception as e:
            print(f"Error compressing image {input_path.name}: {str(e)}")
            self.compression_stats['files_skipped'] += 1
            if progress_callback:
                progress_callback('skipped')
            return False

    def compress_video(self, input_path, output_path, quality=23, use_hardware=True, codec='h264', progress_callback=None):
        try:
            input_path = str(input_path)
            output_path = str(output_path)
            if not output_path.lower().endswith(('.mp4', '.mkv')):
                output_path += '.mp4'

            # Get original file size
            original_size = os.path.getsize(input_path)
            
            # Convert quality value (0-100) to appropriate range for each encoder
            nvenc_quality = int((100 - quality) * 51 / 100)
            crf_quality = int((100 - quality) * 51 / 100)

            stream = ffmpeg.input(input_path)
            output_options = {
                'acodec': 'aac',
                'audio_bitrate': '128k'
            }

            if use_hardware:
                try:
                    if codec == 'h265':
                        output_options.update({
                            'vcodec': 'hevc_nvenc',
                            'preset': 'p4',
                            'rc': 'vbr',
                            'cq': nvenc_quality,
                            'gpu': '0'
                        })
                    else:
                        output_options.update({
                            'vcodec': 'h264_nvenc',
                            'preset': 'p4',
                            'rc': 'vbr',
                            'cq': nvenc_quality,
                            'gpu': '0'
                        })
                except ffmpeg.Error:
                    use_hardware = False

            if not use_hardware:
                output_options.update({
                    'vcodec': 'libx264',
                    'preset': 'medium',
                    'crf': str(crf_quality)
                })

            stream = ffmpeg.output(stream, output_path, **output_options)

            try:
                ffmpeg.run(stream, capture_stdout=True, capture_stderr=True)
                
                # Check if compressed file is larger
                if os.path.getsize(output_path) >= os.path.getsize(input_path):
                    os.remove(output_path)
                    if progress_callback:
                        progress_callback('larger')
                    return False
                    
                # Update compression stats
                self.compression_stats['original_size'] += original_size
                self.compression_stats['compressed_size'] += os.path.getsize(output_path)
                return True
                
            except ffmpeg.Error as e:
                error_message = e.stderr.decode() if e.stderr else str(e)
                print(f"FFmpeg error: {error_message}")
                
                if use_hardware:
                    print("Hardware encoding failed, falling back to software encoding...")
                    return self.compress_video(input_path, output_path, quality, False, 'h264', progress_callback)
                return False

        except Exception as e:
            print(f"Error compressing video: {str(e)}")
            if progress_callback:
                progress_callback('skipped')
            return False

    def compress_file(self, file_path: Path, quality: int = 85) -> bool:
        """Compress a single media file."""
        suffix = file_path.suffix.lower()
        
        if suffix in self.supported_image_formats:
            return self.compress_image(file_path, quality)
        elif suffix in self.supported_video_formats:
            # Create output directory if it doesn't exist
            output_dir = file_path.parent / 'compressed'
            output_dir.mkdir(exist_ok=True)
            
            # Create output path
            output_path = output_dir / f"compressed_{file_path.name}"
            
            # Call compress_video with correct parameters
            return self.compress_video(
                input_path=file_path,
                output_path=output_path,
                quality=quality
            )
        else:
            print(f"Unsupported format: {suffix}")
            return False

    def compress_directory(self, media_files, output_dir, quality, thread_count, progress_callback=None, cancel_check=None, use_hardware=True, codec='h265', replace_files=False):
        """Compress multiple files with progress tracking and cancellation support"""
        total_files = len(media_files)
        successful = 0
        self.compression_stats = {
            'original_size': 0,
            'compressed_size': 0,
            'files_processed': 0,
            'files_skipped': 0
        }

        def update_progress():
            if progress_callback:
                progress_callback({
                    'progress': (successful / total_files * 100) if total_files > 0 else 0,
                    'files_processed': successful,
                    'total_files': total_files
                })

        def process_single_file(file_path):
            nonlocal successful
            
            # Check for cancellation
            if cancel_check and cancel_check():
                return
            
            try:
                output_path = output_dir / file_path.name
                if file_path.suffix.lower() in self.supported_image_formats:
                    result = self.compress_image(file_path, output_path, quality, progress_callback)
                else:
                    result = self.compress_video(file_path, output_path, quality, use_hardware, codec, progress_callback)
                
                if result:
                    successful += 1
                    
                if progress_callback:
                    progress_callback({
                        'progress': (successful / total_files * 100) if total_files > 0 else 0,
                        'files_processed': successful,
                        'total_files': total_files,
                        'current_file': file_path.name
                    })
                    
            except Exception as e:
                print(f"Error processing {file_path}: {e}")
                if progress_callback:
                    progress_callback('error')

        # Process files with thread pool
        with ThreadPoolExecutor(max_workers=thread_count) as executor:
            futures = []
            for f in media_files:
                if cancel_check and cancel_check():
                    executor.shutdown(wait=False)
                    return self._get_stats(total_files, successful)
                futures.append(executor.submit(process_single_file, f))
            
            # Wait for completion and handle errors
            for future in concurrent.futures.as_completed(futures):
                if cancel_check and cancel_check():
                    executor.shutdown(wait=False)
                    break
                try:
                    future.result()
                except Exception as e:
                    print(f"Thread error: {str(e)}")
        
        return self._get_stats(total_files, successful)
    
    def _get_stats(self, total, successful):
        space_saved = self.compression_stats['original_size'] - self.compression_stats['compressed_size']
        ratio = (self.compression_stats['compressed_size'] / self.compression_stats['original_size'] * 100) if self.compression_stats['original_size'] > 0 else 100
        
        return {
            'total_files': total,
            'successful': successful,
            'space_saved': space_saved,
            'ratio': ratio,
            'skipped': self.compression_stats['files_skipped'],
            'original_size': self.compression_stats['original_size'],
            'compressed_size': self.compression_stats['compressed_size']
        }

    def compress_media(self, quality):
        use_hw = self.hw_var.get()
        codec = self.codec_var.get()
        stats = self.compress_directory(self.directory, quality, use_hardware=use_hw, codec=codec)
        
        # Store compression results
        self.compression_results = stats
        self.root.after(0, self.compression_complete)

    @lru_cache(maxsize=1000)
    def get_output_path(self, input_path, directory):
        """Cache output path calculations"""
        return Path(directory) / 'compressed' / input_path.name

    def start_compression(self):
        """Start the compression process"""
        if not hasattr(self, 'directory'):
            messagebox.showerror("Error", "Please select a directory first")
            return

        # Validate quality
        try:
            quality = int(self.quality_var.get())
            if not 1 <= quality <= 100:
                raise ValueError("Quality must be between 1 and 100")
        except ValueError as e:
            messagebox.showerror("Invalid Quality", str(e))
            return

        # Validate thread count
        try:
            thread_count = int(self.thread_var.get())
            max_threads = multiprocessing.cpu_count() * 2
            if not 1 <= thread_count <= max_threads:
                raise ValueError(f"Thread count must be between 1 and {max_threads}")
        except ValueError as e:
            messagebox.showerror("Invalid Thread Count", str(e))
            return

        # Validate file type selection
        if not self.process_images_var.get() and not self.process_videos_var.get():
            messagebox.showerror("Error", "Please select at least one file type to process")
            return

        # Start compression
        self._start_compression_process(quality, thread_count)

    def update_progress(self, progress_info):
        """Update the progress bar and file count with detailed information"""
        if isinstance(progress_info, dict):
            # Update progress bar
            self.progress['value'] = progress_info['progress']
            
            # Update file count with more detail
            processed = progress_info['files_processed']
            total = progress_info['total_files']
            current_file = progress_info.get('current_file', '')
            
            # Calculate estimated time remaining if available
            if 'estimated_time' in progress_info:
                eta = progress_info['estimated_time']
                self.file_count.set(
                    f"Files: {processed}/{total} | ETA: {eta:.1f}s | Current: {current_file}"
                )
            else:
                self.file_count.set(f"Files: {processed}/{total} | Current: {current_file}")
            
            # Show notification for significant events
            if processed > 0 and processed % 10 == 0:  # Every 10 files
                self.show_notification(
                    "Progress Update",
                    f"Processed {processed} of {total} files ({progress_info['progress']:.1f}%)"
                )

    def save_settings(self):
        """Save current settings with error handling and validation"""
        try:
            settings = {
                'quality': int(self.quality_var.get()),
                'threads': int(self.thread_var.get()),
                'hw_acceleration': self.hw_var.get(),
                'codec': self.codec_var.get(),
                'process_images': self.process_images_var.get(),
                'process_videos': self.process_videos_var.get(),
                'replace_files': self.replace_files_var.get(),
                'last_directory': getattr(self, 'directory', '')
            }
            
            # Validate settings before saving
            if not 1 <= settings['quality'] <= 100:
                raise ValueError("Quality must be between 1 and 100")
            if not 1 <= settings['threads'] <= multiprocessing.cpu_count() * 2:
                raise ValueError("Invalid thread count")
                
            # Create settings directory if it doesn't exist
            self.settings_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.settings_file, 'w') as f:
                json.dump(settings, f, indent=4)
                
            self.show_notification("Settings Saved", "Your preferences have been saved successfully")
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not save settings: {e}")

    def create_summary_ui(self, main_frame):
        """Create an enhanced summary UI with charts and detailed statistics"""
        # Title with better styling
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill=tk.X, pady=(0, 20))
        
        ttk.Label(
            title_frame,
            text="Compression Summary",
            style='Header.TLabel'
        ).pack(side=tk.LEFT)
        
        # Add save report button
        ttk.Button(
            title_frame,
            text="Save Report",
            command=self.save_report
        ).pack(side=tk.RIGHT)
        
        # Stats container with better organization
        stats_frame = ttk.Frame(main_frame)
        stats_frame.pack(fill=tk.X, pady=10)
        
        # Create two columns for better layout
        left_frame = ttk.Frame(stats_frame)
        right_frame = ttk.Frame(stats_frame)
        left_frame.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
        right_frame.pack(side=tk.RIGHT, expand=True, fill=tk.BOTH)
        
        # Calculate additional statistics
        total_files = self.compression_results['successful'] + self.compression_results['skipped']
        success_rate = (self.compression_results['successful'] / total_files * 100) if total_files > 0 else 0
        space_saved = self.compression_results['original_size'] - self.compression_results['compressed_size']
        space_saved_percent = (space_saved / self.compression_results['original_size'] * 100) if self.compression_results['original_size'] > 0 else 0
        
        # Add detailed statistics
        self.add_stat(left_frame, "Files Processed", f"{total_files:,}")
        self.add_stat(left_frame, "Success Rate", f"{success_rate:.1f}%")
        self.add_stat(right_frame, "Space Saved", f"{space_saved / (1024*1024):.1f} MB")
        self.add_stat(right_frame, "Reduction", f"{space_saved_percent:.1f}%")

    def add_features(self):
        """Add additional features to enhance user experience"""
        # Add drag and drop support
        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind('<<Drop>>', self.handle_drop)
        
        # Add keyboard shortcuts
        self.root.bind('<Control-o>', lambda e: self.select_directory())
        self.root.bind('<Control-s>', lambda e: self.save_settings())
        self.root.bind('<Escape>', lambda e: self.cancel_compression() if self.compression_in_progress else None)
        
        # Add recent directories menu
        self.recent_dirs = self.load_recent_directories()
        self.create_recent_dirs_menu()
        
        # Add auto-save feature
        self.enable_auto_save()