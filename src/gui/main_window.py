import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import os
import sys
import re
import threading
from datetime import datetime
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except Exception:
    DND_FILES = None
    TkinterDnD = None
try:
    from tkfilebrowser import askopendirnames
except Exception:
    askopendirnames = None
from src import __version__
from src.config_manager import ConfigManager
from src.scheduler_manager import SchedulerManager
from src.backup_engine import BackupEngine
from src.updater import Updater

class MainWindow(TkinterDnD.Tk if TkinterDnD is not None else tk.Tk):
    def __init__(self, config_manager):
        super().__init__()
        self.config_manager = config_manager
        self.scheduler_manager = SchedulerManager()
        
        self.title(f"k_backups v{__version__} - Backup Utility")
        self.geometry("800x600")
        
        # Set window icon if available
        # Check both relative path (for dev) and sys._MEIPASS (for PyInstaller)
        icon_path = os.path.join("assets", "app_icon.ico")
        if not os.path.exists(icon_path) and hasattr(sys, '_MEIPASS'):
             icon_path = os.path.join(sys._MEIPASS, "assets", "app_icon.ico")
             
        if os.path.exists(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception as e:
                print(f"Icon loading failed: {e}")
        
        # Apply theme
        self._apply_theme()
        
        # Create Notebook (Tabs)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Tabs
        self.tab_dashboard = ttk.Frame(self.notebook)
        self.tab_jobs = ttk.Frame(self.notebook)
        self.tab_settings = ttk.Frame(self.notebook) # NAS settings
        self.tab_restore = ttk.Frame(self.notebook)
        
        self.notebook.add(self.tab_dashboard, text="Dashboard")
        self.notebook.add(self.tab_jobs, text="Manage Jobs")
        self.notebook.add(self.tab_settings, text="Settings")
        self.notebook.add(self.tab_restore, text="Restore")
        
        # Initialize tabs
        self._init_dashboard_tab()
        self._init_jobs_tab()
        self._init_settings_tab()
        self._init_restore_tab()

        # Auto-check for updates silently on startup (non-blocking)
        self.after(2500, lambda: threading.Thread(target=self._auto_check_updates, daemon=True).start())

    def _apply_theme(self):
        """Attempts to apply the Azure Dark theme."""
        # Check if theme file exists in assets
        theme_file = os.path.join("assets", "azure.tcl")
        if os.path.exists(theme_file):
            try:
                self.tk.call("source", theme_file)
                self.tk.call("set_theme", "dark")
            except Exception as e:
                print(f"Failed to load theme: {e}")
        else:
            # Fallback style
            style = ttk.Style()
            style.theme_use('clam')
            
            # Colors
            bg_color = "#2b2b2b"
            fg_color = "#ffffff"
            accent_color = "#007acc"
            active_bg = "#3c3c3c"
            
            style.configure(".", background=bg_color, foreground=fg_color, fieldbackground=active_bg, darkcolor=bg_color, lightcolor=bg_color, bordercolor=bg_color)
            style.configure("TLabel", background=bg_color, foreground=fg_color)
            style.configure("TButton", background=active_bg, foreground=fg_color, borderwidth=1, focusthickness=3, focuscolor=accent_color)
            style.map("TButton", background=[("active", accent_color), ("pressed", accent_color)], foreground=[("active", "white")])
            
            style.configure("TEntry", fieldbackground=active_bg, foreground=fg_color, insertcolor=fg_color)
            
            # Notebook (Tabs)
            style.configure("TNotebook", background=bg_color, borderwidth=0)
            style.configure("TNotebook.Tab", background=active_bg, foreground=fg_color, padding=[10, 5], borderwidth=0)
            style.map("TNotebook.Tab", background=[("selected", accent_color)], foreground=[("selected", "white")])
            
            # Treeview
            style.configure("Treeview", background=active_bg, foreground=fg_color, fieldbackground=active_bg, borderwidth=0)
            style.configure("Treeview.Heading", background=bg_color, foreground=fg_color, relief="flat")
            style.map("Treeview.Heading", background=[("active", active_bg)])
            
            # Labelframes
            style.configure("TLabelframe", background=bg_color, bordercolor=active_bg)
            style.configure("TLabelframe.Label", background=bg_color, foreground=accent_color)
            
            # Combobox
            style.map("TCombobox", fieldbackground=[("readonly", active_bg)], selectbackground=[("readonly", active_bg)], selectforeground=[("readonly", fg_color)], background=[("readonly", active_bg)], foreground=[("readonly", fg_color)])
            # This handles the dropdown listbox
            self.option_add("*TCombobox*Listbox.background", active_bg)
            self.option_add("*TCombobox*Listbox.foreground", fg_color)
            self.option_add("*TCombobox*Listbox.selectBackground", accent_color)
            self.option_add("*TCombobox*Listbox.selectForeground", "white")
            
            self.configure(bg=bg_color)

    def _init_dashboard_tab(self):
        # Job Selection
        frame_top = ttk.Frame(self.tab_dashboard)
        frame_top.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(frame_top, text="Select Job:").pack(side=tk.LEFT)
        self.combo_jobs = ttk.Combobox(frame_top, state="readonly")
        self.combo_jobs.pack(side=tk.LEFT, padx=5)
        self._refresh_jobs_list()
        
        # Actions
        frame_actions = ttk.Frame(self.tab_dashboard)
        frame_actions.pack(pady=10)
        
        self.btn_backup = ttk.Button(frame_actions, text="Backup Now", command=self._start_backup)
        self.btn_backup.pack(side=tk.LEFT, padx=5)

        self.btn_pause = ttk.Button(frame_actions, text="Pause", command=self._pause_backup, state="disabled")
        self.btn_pause.pack(side=tk.LEFT, padx=5)

        self.btn_stop = ttk.Button(frame_actions, text="Stop", command=self._stop_backup, state="disabled")
        self.btn_stop.pack(side=tk.LEFT, padx=5)
        
        # Progress
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.tab_dashboard, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, padx=20, pady=5)
        
        self.lbl_status = ttk.Label(self.tab_dashboard, text="Ready")
        self.lbl_status.pack(pady=5)

        # Settings file status
        frame_settings_status = ttk.LabelFrame(self.tab_dashboard, text="Settings File")
        frame_settings_status.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.lbl_settings_path = ttk.Label(frame_settings_status, text="")
        self.lbl_settings_path.pack(anchor=tk.W, padx=8, pady=(6, 2))

        self.lbl_settings_state = ttk.Label(frame_settings_status, text="")
        self.lbl_settings_state.pack(anchor=tk.W, padx=8, pady=(0, 8))

        self._refresh_settings_file_status()

        # Log Area
        frame_logs = ttk.LabelFrame(self.tab_dashboard, text="Activity Log")
        frame_logs.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.log_area = scrolledtext.ScrolledText(frame_logs, height=10, state='disabled', bg="#1e1e1e", fg="#d4d4d4", font=("Consolas", 9))
        self.log_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _log(self, message):
        self.log_area.config(state='normal')
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)
        self.log_area.config(state='disabled')

    def _normalize_destination_path(self, path):
        normalized = path.strip().replace("/", "\\")

        # If user started with one or more slashes, normalize to UNC double backslash.
        if normalized.startswith("\\"):
            normalized = "\\\\" + normalized.lstrip("\\")

        return normalized

    def _select_source_folders(self, parent):
        if askopendirnames is not None:
            try:
                selected_paths = askopendirnames(parent=parent, title="Select Source Folder(s)")
                return [path for path in selected_paths if path]
            except Exception:
                pass

        selected_path = filedialog.askdirectory(title="Select Source Folder", parent=parent)
        return [selected_path] if selected_path else []

    def _parse_dropped_paths(self, raw_data):
        if not raw_data:
            return []

        try:
            parts = self.tk.splitlist(raw_data)
        except Exception:
            parts = [raw_data]

        parsed = []
        for part in parts:
            normalized = part.strip().strip("{}").strip('"')
            if normalized:
                parsed.append(os.path.normpath(normalized))

        return parsed

    def _enable_source_list_drop(self, listbox):
        if DND_FILES is None:
            return

        def on_drop(event):
            dropped_paths = self._parse_dropped_paths(event.data)
            existing_paths = set(listbox.get(0, tk.END))

            for dropped_path in dropped_paths:
                if os.path.isdir(dropped_path) and dropped_path not in existing_paths:
                    listbox.insert(tk.END, dropped_path)
                    existing_paths.add(dropped_path)

            return "break"

        try:
            listbox.drop_target_register(DND_FILES)
            listbox.dnd_bind("<<Drop>>", on_drop)
        except Exception:
            pass

    def _refresh_settings_file_status(self):
        config_path = os.path.abspath(self.config_manager.config_path)
        self.lbl_settings_path.config(text=f"Path: {config_path}")

        if os.path.exists(config_path):
            try:
                modified = datetime.fromtimestamp(os.path.getmtime(config_path)).strftime("%Y-%m-%d %H:%M:%S")
                self.lbl_settings_state.config(text=f"Status: Found | Last updated: {modified}")
            except Exception:
                self.lbl_settings_state.config(text="Status: Found")
        else:
            self.lbl_settings_state.config(text="Status: Missing")

    def _pause_backup(self):
        if hasattr(self, 'current_engine') and self.current_engine:
            if self.btn_pause['text'] == "Pause":
                self.current_engine.request_pause()
                self.btn_pause.config(text="Resume")
                self._log("Backup paused...")
            else:
                self.current_engine.resume()
                self.btn_pause.config(text="Pause")
                self._log("Backup resumed...")

    def _stop_backup(self):
        if hasattr(self, 'current_engine') and self.current_engine:
            self.current_engine.request_stop()
            self._log("Stop requested... waiting for current operation to finish.")
            self.btn_stop.state(['disabled'])
            self.btn_pause.state(['disabled'])


    def _init_jobs_tab(self):
        # Frame for list + buttons
        frame_list = ttk.Frame(self.tab_jobs)
        frame_list.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Columns: Name, Source, Destination
        self.tree_jobs = ttk.Treeview(frame_list, columns=("name", "source", "dest"), show="headings")
        self.tree_jobs.heading("name", text="Name")
        self.tree_jobs.heading("source", text="Source")
        self.tree_jobs.heading("dest", text="Destination")
        
        self.tree_jobs.column("name", width=100)
        self.tree_jobs.column("source", width=200)
        self.tree_jobs.column("dest", width=100)
        
        self.tree_jobs.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(frame_list, orient="vertical", command=self.tree_jobs.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_jobs.configure(yscrollcommand=scrollbar.set)
        
        # Buttons
        frame_btns = ttk.Frame(self.tab_jobs)
        frame_btns.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(frame_btns, text="Add Job", command=self._add_job).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame_btns, text="Edit Job", command=self._edit_job).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame_btns, text="Delete Job", command=self._delete_job).pack(side=tk.LEFT, padx=5)
        
        self._refresh_jobs_tree()

    def _refresh_jobs_tree(self):
        for i in self.tree_jobs.get_children():
            self.tree_jobs.delete(i)
            
        jobs = self.config_manager.get_jobs()
        for idx, job in enumerate(jobs):
            # Source path list to string
            sources = ", ".join(job.get("source_paths", []))
            self.tree_jobs.insert("", "end", iid=idx, values=(
                job.get("name"),
                sources,
                job.get("destination_path")
            ))

    def _add_job(self):
        top = tk.Toplevel(self)
        top.title("Add New Job")
        top.geometry("600x600")
        top.transient(self)
        top.grab_set()
        top.lift()
        top.focus_force()
        
        # Apply dark background
        bg_color = "#2b2b2b"
        top.configure(bg=bg_color)
        
        # Main container with padding
        main_frame = ttk.Frame(top, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Job Name
        ttk.Label(main_frame, text="Job Name:").pack(anchor=tk.W, pady=(0, 5))
        ent_name = ttk.Entry(main_frame)
        ent_name.pack(fill=tk.X, pady=(0, 15))
        
        # Source Folders (Listbox)
        ttk.Label(main_frame, text="Source Folders:").pack(anchor=tk.W, pady=(0, 5))
        
        frame_sources = ttk.Frame(main_frame)
        frame_sources.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        
        list_sources = tk.Listbox(frame_sources, height=6, bg="#3c3c3c", fg="#ffffff", selectbackground="#007acc", borderwidth=0)
        list_sources.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar_sources = ttk.Scrollbar(frame_sources, orient="vertical", command=list_sources.yview)
        scrollbar_sources.pack(side=tk.RIGHT, fill=tk.Y)
        list_sources.config(yscrollcommand=scrollbar_sources.set)

        self._enable_source_list_drop(list_sources)
        
        # Source Buttons
        frame_source_btns = ttk.Frame(main_frame)
        frame_source_btns.pack(fill=tk.X, pady=(0, 15))
        
        def add_source():
            selected_paths = self._select_source_folders(top)
            existing_paths = set(list_sources.get(0, tk.END))
            for selected_path in selected_paths:
                if selected_path not in existing_paths:
                    list_sources.insert(tk.END, selected_path)
                    existing_paths.add(selected_path)
            top.lift()
            top.focus_force()
        
        def remove_source():
            selection = list_sources.curselection()
            if selection:
                list_sources.delete(selection[0])
                
        ttk.Button(frame_source_btns, text="Add Folder", command=add_source).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(frame_source_btns, text="Remove Selected", command=remove_source).pack(side=tk.LEFT)

        if DND_FILES is not None:
            ttk.Label(
                main_frame,
                text="Tip: Drag and drop folder(s) from Explorer into the source list.",
                font=("Segoe UI", 8)
            ).pack(anchor=tk.W, pady=(0, 12))

        # Destination Folder
        ttk.Label(main_frame, text="Destination Folder (on NAS):").pack(anchor=tk.W, pady=(0, 5))
        
        frame_dest = ttk.Frame(main_frame)
        frame_dest.pack(fill=tk.X, pady=(0, 5))
        
        ent_dest = ttk.Entry(frame_dest)
        ent_dest.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        def browse_dest():
            # Note: Browsing network locations might require user to select mapped drive or Network in dialog
            d = filedialog.askdirectory(title="Select Destination Folder", parent=top)
            if d:
                # If path is irrelevant (e.g. user wants to type UNC), they can still type.
                ent_dest.delete(0, tk.END)
                ent_dest.insert(0, d)
            top.lift()
            top.focus_force()
                
        ttk.Button(frame_dest, text="Browse...", command=browse_dest).pack(side=tk.LEFT)
        
        ttk.Label(main_frame, text="Note: For NAS, use UNC path if not mapped (e.g. \\\\Server\\Share\\Folder)", font=("Segoe UI", 8)).pack(anchor=tk.W, pady=(0, 20))

        # Save / Cancel
        frame_actions = ttk.Frame(main_frame)
        frame_actions.pack(fill=tk.X, side=tk.BOTTOM)
        
        def save():
            name = ent_name.get().strip()
            sources = list(list_sources.get(0, tk.END))
            dest = self._normalize_destination_path(ent_dest.get())
            ent_dest.delete(0, tk.END)
            ent_dest.insert(0, dest)
            
            if not name:
                messagebox.showwarning("Error", "Job Name is required.", parent=top)
                return
            if not sources:
                messagebox.showwarning("Error", "At least one Source Folder is required.", parent=top)
                return
            if not dest:
                messagebox.showwarning("Error", "Destination Folder is required.", parent=top)
                return
                
            job_data = {
                "name": name,
                "source_paths": sources,
                "destination_path": dest,
                "exclude_patterns": [],
                "schedule": self._default_job_schedule(name)
            }
            try:
                self.config_manager.add_job(job_data)
                self._refresh_all_job_lists(preferred_job_name=name)
                top.destroy()
                messagebox.showinfo("Success", f"Job '{name}' created successfully.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save job: {e}", parent=top)
            
        ttk.Button(frame_actions, text="Save Job", command=save).pack(side=tk.RIGHT)
        ttk.Button(frame_actions, text="Cancel", command=top.destroy).pack(side=tk.RIGHT, padx=(0, 10))

    def _delete_job(self):
        selected = self.tree_jobs.selection()
        if not selected:
            return
        idx = int(selected[0])
        if messagebox.askyesno("Confirm", "Delete selected job?"):
            jobs = self.config_manager.get_jobs()
            if 0 <= idx < len(jobs):
                job = jobs[idx]
                schedule = job.get("schedule", {})
                task_name = (schedule.get("task_name") or self._default_task_name_for_job(job.get("name", "job"))).strip()
                if task_name and self.scheduler_manager.task_exists(task_name):
                    self.scheduler_manager.remove_reminder(task_name)

            self.config_manager.delete_job(idx)
            self._refresh_all_job_lists()

    def _edit_job(self):
        selected = self.tree_jobs.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a job to edit.")
            return

        job_index = int(selected[0])
        jobs = self.config_manager.get_jobs()
        if job_index < 0 or job_index >= len(jobs):
            messagebox.showerror("Error", "Selected job no longer exists.")
            self._refresh_all_job_lists()
            return

        existing_job = jobs[job_index]

        top = tk.Toplevel(self)
        top.title("Edit Job")
        top.geometry("600x600")
        top.transient(self)
        top.grab_set()
        top.lift()
        top.focus_force()

        bg_color = "#2b2b2b"
        top.configure(bg=bg_color)

        main_frame = ttk.Frame(top, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Job Name:").pack(anchor=tk.W, pady=(0, 5))
        ent_name = ttk.Entry(main_frame)
        ent_name.pack(fill=tk.X, pady=(0, 15))
        ent_name.insert(0, existing_job.get("name", ""))

        ttk.Label(main_frame, text="Source Folders:").pack(anchor=tk.W, pady=(0, 5))

        frame_sources = ttk.Frame(main_frame)
        frame_sources.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        list_sources = tk.Listbox(frame_sources, height=6, bg="#3c3c3c", fg="#ffffff", selectbackground="#007acc", borderwidth=0)
        list_sources.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar_sources = ttk.Scrollbar(frame_sources, orient="vertical", command=list_sources.yview)
        scrollbar_sources.pack(side=tk.RIGHT, fill=tk.Y)
        list_sources.config(yscrollcommand=scrollbar_sources.set)

        self._enable_source_list_drop(list_sources)

        for source_path in existing_job.get("source_paths", []):
            list_sources.insert(tk.END, source_path)

        frame_source_btns = ttk.Frame(main_frame)
        frame_source_btns.pack(fill=tk.X, pady=(0, 15))

        def add_source():
            selected_paths = self._select_source_folders(top)
            existing_paths = set(list_sources.get(0, tk.END))
            for selected_path in selected_paths:
                if selected_path not in existing_paths:
                    list_sources.insert(tk.END, selected_path)
                    existing_paths.add(selected_path)
            top.lift()
            top.focus_force()

        def remove_source():
            selection = list_sources.curselection()
            if selection:
                list_sources.delete(selection[0])

        ttk.Button(frame_source_btns, text="Add Folder", command=add_source).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(frame_source_btns, text="Remove Selected", command=remove_source).pack(side=tk.LEFT)

        if DND_FILES is not None:
            ttk.Label(
                main_frame,
                text="Tip: Drag and drop folder(s) from Explorer into the source list.",
                font=("Segoe UI", 8)
            ).pack(anchor=tk.W, pady=(0, 12))

        ttk.Label(main_frame, text="Destination Folder (on NAS):").pack(anchor=tk.W, pady=(0, 5))

        frame_dest = ttk.Frame(main_frame)
        frame_dest.pack(fill=tk.X, pady=(0, 5))

        ent_dest = ttk.Entry(frame_dest)
        ent_dest.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ent_dest.insert(0, existing_job.get("destination_path", ""))

        def browse_dest():
            d = filedialog.askdirectory(title="Select Destination Folder", parent=top)
            if d:
                ent_dest.delete(0, tk.END)
                ent_dest.insert(0, d)
            top.lift()
            top.focus_force()

        ttk.Button(frame_dest, text="Browse...", command=browse_dest).pack(side=tk.LEFT)

        ttk.Label(main_frame, text="Note: For NAS, use UNC path if not mapped (e.g. \\\\Server\\Share\\Folder)", font=("Segoe UI", 8)).pack(anchor=tk.W, pady=(0, 20))

        frame_actions = ttk.Frame(main_frame)
        frame_actions.pack(fill=tk.X, side=tk.BOTTOM)

        def save_changes():
            name = ent_name.get().strip()
            sources = list(list_sources.get(0, tk.END))
            dest = self._normalize_destination_path(ent_dest.get())
            ent_dest.delete(0, tk.END)
            ent_dest.insert(0, dest)

            if not name:
                messagebox.showwarning("Error", "Job Name is required.", parent=top)
                return
            if not sources:
                messagebox.showwarning("Error", "At least one Source Folder is required.", parent=top)
                return
            if not dest:
                messagebox.showwarning("Error", "Destination Folder is required.", parent=top)
                return

            job_data = existing_job.copy()
            job_data.update({
                "name": name,
                "source_paths": sources,
                "destination_path": dest,
                "exclude_patterns": existing_job.get("exclude_patterns", [])
            })

            try:
                updated = self.config_manager.update_job(job_index, job_data)
                if not updated:
                    messagebox.showerror("Error", "Failed to update job.", parent=top)
                    return

                self._refresh_all_job_lists(preferred_job_name=name)
                top.destroy()
                messagebox.showinfo("Success", f"Job '{name}' updated successfully.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update job: {e}", parent=top)

        ttk.Button(frame_actions, text="Save Changes", command=save_changes).pack(side=tk.RIGHT)
        ttk.Button(frame_actions, text="Cancel", command=top.destroy).pack(side=tk.RIGHT, padx=(0, 10))

    def _init_settings_tab(self):
        # NAS Settings
        frame_nas = ttk.LabelFrame(self.tab_settings, text="NAS Connection")
        frame_nas.pack(fill=tk.X, padx=10, pady=10)
        
        # Address
        ttk.Label(frame_nas, text="Address (UNC):").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.ent_nas_address = ttk.Entry(frame_nas, width=40)
        self.ent_nas_address.grid(row=0, column=1, padx=5, pady=5)
        
        # Username
        ttk.Label(frame_nas, text="Username:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.ent_nas_user = ttk.Entry(frame_nas, width=30)
        self.ent_nas_user.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        
        # Password
        ttk.Label(frame_nas, text="Password:").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        self.ent_nas_pass = ttk.Entry(frame_nas, show="*", width=30)
        self.ent_nas_pass.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        
        # Save Button
        ttk.Button(frame_nas, text="Save Settings", command=self._save_nas_settings).grid(row=3, column=1, pady=10)

        # Scheduler (per-job)
        frame_scheduler = ttk.LabelFrame(self.tab_settings, text="Job Reminder Schedule")
        frame_scheduler.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(frame_scheduler, text="Job:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.combo_schedule_job = ttk.Combobox(frame_scheduler, state="readonly", width=30)
        self.combo_schedule_job.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        self.combo_schedule_job.bind("<<ComboboxSelected>>", self._on_schedule_job_selected)

        self.var_schedule_enabled = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame_scheduler, text="Enabled", variable=self.var_schedule_enabled).grid(row=1, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(frame_scheduler, text="Task Name:").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        self.ent_schedule_task_name = ttk.Entry(frame_scheduler, width=40)
        self.ent_schedule_task_name.grid(row=2, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(frame_scheduler, text="Reminder Message:").grid(row=3, column=0, padx=5, pady=5, sticky="e")
        self.ent_schedule_message = ttk.Entry(frame_scheduler, width=50)
        self.ent_schedule_message.grid(row=3, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(frame_scheduler, text="Recurrence:").grid(row=4, column=0, padx=5, pady=5, sticky="e")
        self.combo_schedule_recurrence = ttk.Combobox(frame_scheduler, state="readonly", values=["Weekly", "Monthly"], width=15)
        self.combo_schedule_recurrence.grid(row=4, column=1, padx=5, pady=5, sticky="w")
        self.combo_schedule_recurrence.bind("<<ComboboxSelected>>", self._on_schedule_recurrence_changed)

        ttk.Label(frame_scheduler, text="Time (HH:MM):").grid(row=5, column=0, padx=5, pady=5, sticky="e")
        self.ent_schedule_time = ttk.Entry(frame_scheduler, width=10)
        self.ent_schedule_time.grid(row=5, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(frame_scheduler, text="Weekly Day:").grid(row=6, column=0, padx=5, pady=5, sticky="e")
        self.combo_schedule_weekday = ttk.Combobox(
            frame_scheduler,
            state="readonly",
            values=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
            width=15
        )
        self.combo_schedule_weekday.grid(row=6, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(frame_scheduler, text="Monthly Day (1-31):").grid(row=7, column=0, padx=5, pady=5, sticky="e")
        self.spin_schedule_dom = tk.Spinbox(frame_scheduler, from_=1, to=31, width=7)
        self.spin_schedule_dom.grid(row=7, column=1, padx=5, pady=5, sticky="w")

        frame_schedule_actions = ttk.Frame(frame_scheduler)
        frame_schedule_actions.grid(row=8, column=1, padx=5, pady=10, sticky="w")
        ttk.Button(frame_schedule_actions, text="Save Schedule", command=self._save_job_schedule).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(frame_schedule_actions, text="Remove Schedule", command=self._remove_job_schedule).pack(side=tk.LEFT)

        self.lbl_schedule_status = ttk.Label(frame_scheduler, text="")
        self.lbl_schedule_status.grid(row=9, column=0, columnspan=2, padx=5, pady=(0, 5), sticky="w")
        
        # Load existing
        nas_config = self.config_manager.get_nas_settings()
        self.ent_nas_address.insert(0, nas_config.get("address", ""))
        self.ent_nas_user.insert(0, nas_config.get("username", ""))
        self.ent_nas_pass.insert(0, nas_config.get("password", ""))

        self._refresh_schedule_jobs()

        # Updates
        frame_updates = ttk.LabelFrame(self.tab_settings, text="Application Updates")
        frame_updates.pack(fill=tk.X, padx=10, pady=10)

        self.lbl_update_status = ttk.Label(frame_updates, text=f"Version {__version__}")
        self.lbl_update_status.pack(anchor=tk.W, padx=8, pady=(6, 2))

        ttk.Button(frame_updates, text="Check for Updates", command=self._check_for_updates).pack(anchor=tk.W, padx=8, pady=(4, 8))

    def _init_restore_tab(self):
        frame_top = ttk.Frame(self.tab_restore)
        frame_top.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(frame_top, text="Select Job to Restore:").pack(side=tk.LEFT)
        self.combo_restore_jobs = ttk.Combobox(frame_top, state="readonly")
        self.combo_restore_jobs.pack(side=tk.LEFT, padx=5)
        
        # We need to refresh this list too when jobs change
        # For now populate once
        self._refresh_restore_jobs()
        
        frame_dest = ttk.Frame(self.tab_restore)
        frame_dest.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(frame_dest, text="Restore To:").pack(side=tk.LEFT)
        self.ent_restore_dest = ttk.Entry(frame_dest, width=40)
        self.ent_restore_dest.pack(side=tk.LEFT, padx=5)
        
        def browse_restore_dest():
            d = filedialog.askdirectory()
            if d:
                self.ent_restore_dest.delete(0, tk.END)
                self.ent_restore_dest.insert(0, d)
        
        ttk.Button(frame_dest, text="Browse...", command=browse_restore_dest).pack(side=tk.LEFT)
        
        frame_action = ttk.Frame(self.tab_restore)
        frame_action.pack(pady=20)
        
        ttk.Button(frame_action, text="Start Full Restore", command=self._start_restore).pack()
        
        self.lbl_restore_status = ttk.Label(self.tab_restore, text="")
        self.lbl_restore_status.pack(pady=5)

    def _refresh_restore_jobs(self):
        jobs = self.config_manager.get_jobs()
        names = [j['name'] for j in jobs]
        self.combo_restore_jobs['values'] = names
        if names: self.combo_restore_jobs.current(0)
        
    def _start_restore(self):
        job_name = self.combo_restore_jobs.get()
        dest = self.ent_restore_dest.get()
        
        if not job_name or not dest:
            messagebox.showwarning("Error", "Please select a job and destination folder.")
            return
            
        if not os.path.exists(dest):
            if messagebox.askyesno("Create Folder", f"Folder {dest} does not exist. Create it?"):
                os.makedirs(dest)
            else:
                return

        self.lbl_restore_status.config(text="Starting restore...")
        threading.Thread(target=self._run_restore_thread, args=(job_name, dest), daemon=True).start()

    def _run_restore_thread(self, job_name, dest):
        engine = BackupEngine(self.config_manager)
        
        def progress_callback(processed, total, msg):
             self.after(0, lambda: self.lbl_restore_status.config(text=msg))
             
        success = engine.restore_job(job_name, dest, progress_callback)
        
        if success:
            self.after(0, lambda: messagebox.showinfo("Restore", "Restore completed successfully!"))
        else:
            self.after(0, lambda: messagebox.showerror("Restore", "Restore failed. Check logs."))

    def _save_nas_settings(self):
        addr = self.ent_nas_address.get()
        user = self.ent_nas_user.get()
        pwd = self.ent_nas_pass.get()
        self.config_manager.set_nas_settings(addr, user, pwd)
        self._refresh_settings_file_status()
        messagebox.showinfo("Saved", "NAS settings saved successfully.")

    def _refresh_all_job_lists(self, preferred_job_name=None):
        self._refresh_jobs_list(preferred_job_name=preferred_job_name)
        self._refresh_jobs_tree()
        self._refresh_restore_jobs(preferred_job_name=preferred_job_name)
        self._refresh_schedule_jobs(preferred_job_name=preferred_job_name)

    def _refresh_jobs_list(self, preferred_job_name=None):
        jobs = self.config_manager.get_jobs()
        job_names = [j['name'] for j in jobs]
        self.combo_jobs['values'] = job_names
        if not job_names:
            self.combo_jobs.set("")
            return

        if preferred_job_name and preferred_job_name in job_names:
            self.combo_jobs.set(preferred_job_name)
            return

        current_value = self.combo_jobs.get()
        if current_value not in job_names:
            self.combo_jobs.current(0)

    def _refresh_restore_jobs(self, preferred_job_name=None):
        jobs = self.config_manager.get_jobs()
        names = [j['name'] for j in jobs]
        if hasattr(self, 'combo_restore_jobs'):
            self.combo_restore_jobs['values'] = names

            if not names:
                self.combo_restore_jobs.set("")
                return

            if preferred_job_name and preferred_job_name in names:
                self.combo_restore_jobs.set(preferred_job_name)
                return

            current_value = self.combo_restore_jobs.get()
            if current_value not in names:
                self.combo_restore_jobs.current(0)

    def _start_backup(self):
        job_name = self.combo_jobs.get()
        if not job_name:
            messagebox.showwarning("Warning", "Please select a job first.")
            return

        self.btn_backup.state(['disabled'])
        self.btn_pause.state(['!disabled'])
        self.btn_stop.state(['!disabled'])
        self.btn_pause.config(text="Pause") # Reset text
        
        self.lbl_status.config(text="Starting backup...")
        self.progress_var.set(0)
        
        # Clear log area
        self.log_area.config(state='normal')
        self.log_area.delete('1.0', tk.END)
        self.log_area.config(state='disabled')
        
        # Run in thread
        threading.Thread(target=self._run_backup_thread, args=(job_name,), daemon=True).start()

    def _run_backup_thread(self, job_name):
        self.current_engine = BackupEngine(self.config_manager)
        
        def progress_callback(processed, total, msg):
            # Update UI from thread safely
            if total > 0:
                pct = (processed / total) * 100
                self.after(0, lambda: self.progress_var.set(pct))
            
            self.after(0, lambda: self.lbl_status.config(text=msg))
            # Log to text area
            if msg and ("Uploading" in msg or "Deleting" in msg or "Error" in msg or "failed" in msg or "Scanning" in msg or "completed" in msg):
                 self.after(0, lambda: self._log(msg))

        try:
            success = self.current_engine.run_job(job_name, progress_callback)
        except Exception as e:
            success = False
            self.after(0, lambda: self._log(f"Critical Error: {e}"))

        # Cleanup UI
        def cleanup():
            self.btn_backup.state(['!disabled'])
            self.btn_pause.state(['disabled'])
            self.btn_stop.state(['disabled'])
            self.current_engine = None
            if success:
                messagebox.showinfo("Backup", "Backup completed successfully!")
            else:
                messagebox.showerror("Backup", "Backup failed or stopped. Check logs.")

        self.after(0, cleanup)

    def _sanitize_task_token(self, value):
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", (value or "").strip())
        return safe.strip("_") or "job"

    def _default_task_name_for_job(self, job_name):
        return f"k_backups_reminder_{self._sanitize_task_token(job_name)}"

    def _default_job_schedule(self, job_name):
        return {
            "enabled": False,
            "recurrence": "Weekly",
            "time": "09:00",
            "day_of_week": "Monday",
            "day_of_month": 1,
            "task_name": self._default_task_name_for_job(job_name),
            "message": f"Reminder: run backup job '{job_name}'."
        }

    def _get_job_by_name(self, job_name):
        jobs = self.config_manager.get_jobs()
        for index, job in enumerate(jobs):
            if job.get("name") == job_name:
                return index, job
        return None, None

    def _refresh_schedule_jobs(self, preferred_job_name=None):
        if not hasattr(self, 'combo_schedule_job'):
            return

        jobs = self.config_manager.get_jobs()
        names = [job.get("name", "") for job in jobs if job.get("name")]
        self.combo_schedule_job['values'] = names

        if not names:
            self.combo_schedule_job.set("")
            self.lbl_schedule_status.config(text="No jobs available. Create a job first.")
            return

        if preferred_job_name and preferred_job_name in names:
            selected_name = preferred_job_name
        else:
            current = self.combo_schedule_job.get()
            selected_name = current if current in names else names[0]

        self.combo_schedule_job.set(selected_name)
        self._on_schedule_job_selected()

    def _on_schedule_recurrence_changed(self, event=None):
        recurrence = (self.combo_schedule_recurrence.get() or "Weekly").strip().lower()
        if recurrence == "weekly":
            self.combo_schedule_weekday.configure(state="readonly")
            self.spin_schedule_dom.configure(state="disabled")
        else:
            self.combo_schedule_weekday.configure(state="disabled")
            self.spin_schedule_dom.configure(state="normal")

    def _on_schedule_job_selected(self, event=None):
        job_name = self.combo_schedule_job.get()
        _, job = self._get_job_by_name(job_name)
        if not job:
            return

        schedule = job.get("schedule") or self._default_job_schedule(job_name)
        self.var_schedule_enabled.set(bool(schedule.get("enabled", False)))
        self.combo_schedule_recurrence.set(schedule.get("recurrence", "Weekly"))
        self.ent_schedule_time.delete(0, tk.END)
        self.ent_schedule_time.insert(0, schedule.get("time", "09:00"))

        self.combo_schedule_weekday.set(schedule.get("day_of_week", "Monday"))

        self.spin_schedule_dom.delete(0, tk.END)
        self.spin_schedule_dom.insert(0, str(schedule.get("day_of_month", 1)))

        task_name = schedule.get("task_name") or self._default_task_name_for_job(job_name)
        self.ent_schedule_task_name.delete(0, tk.END)
        self.ent_schedule_task_name.insert(0, task_name)

        message_text = schedule.get("message") or f"Reminder: run backup job '{job_name}'."
        self.ent_schedule_message.delete(0, tk.END)
        self.ent_schedule_message.insert(0, message_text)

        self._on_schedule_recurrence_changed()
        self.lbl_schedule_status.config(text=f"Editing schedule for job: {job_name}")

    def _build_schedule_from_form(self, job_name):
        recurrence = (self.combo_schedule_recurrence.get() or "Weekly").strip().title()
        if recurrence not in ("Weekly", "Monthly"):
            raise ValueError("Recurrence must be Weekly or Monthly.")

        run_time = (self.ent_schedule_time.get() or "").strip()
        if not run_time:
            raise ValueError("Time is required in HH:MM format.")

        task_name = (self.ent_schedule_task_name.get() or "").strip()
        if not task_name:
            task_name = self._default_task_name_for_job(job_name)

        message_text = (self.ent_schedule_message.get() or "").strip()
        if not message_text:
            message_text = f"Reminder: run backup job '{job_name}'."

        day_of_week = (self.combo_schedule_weekday.get() or "Monday").strip().title()
        try:
            day_of_month = int((self.spin_schedule_dom.get() or "1").strip())
        except ValueError:
            raise ValueError("Monthly day must be a number between 1 and 31.")

        if day_of_month < 1 or day_of_month > 31:
            raise ValueError("Monthly day must be between 1 and 31.")

        return {
            "enabled": bool(self.var_schedule_enabled.get()),
            "recurrence": recurrence,
            "time": run_time,
            "day_of_week": day_of_week,
            "day_of_month": day_of_month,
            "task_name": task_name,
            "message": message_text,
        }

    def _save_job_schedule(self):
        job_name = self.combo_schedule_job.get()
        if not job_name:
            messagebox.showwarning("Schedule", "Select a job first.")
            return

        job_index, existing_job = self._get_job_by_name(job_name)
        if existing_job is None:
            messagebox.showerror("Schedule", "Selected job no longer exists.")
            self._refresh_schedule_jobs()
            return

        try:
            schedule = self._build_schedule_from_form(job_name)
        except ValueError as validation_error:
            messagebox.showwarning("Schedule", str(validation_error))
            return

        old_schedule = existing_job.get("schedule", {})
        old_task_name = (old_schedule.get("task_name") or "").strip()
        new_task_name = schedule["task_name"]

        if schedule["enabled"]:
            created = self.scheduler_manager.create_or_update_reminder(
                task_name=new_task_name,
                recurrence=schedule["recurrence"],
                run_time=schedule["time"],
                reminder_message=schedule["message"],
                day_of_week=schedule["day_of_week"],
                day_of_month=schedule["day_of_month"],
            )
            if not created:
                messagebox.showerror("Schedule", "Failed to create/update schedule task. Check logs and task permissions.")
                return

            self.scheduler_manager.set_task_enabled(new_task_name, True)
        else:
            if self.scheduler_manager.task_exists(new_task_name):
                if not self.scheduler_manager.set_task_enabled(new_task_name, False):
                    messagebox.showerror("Schedule", "Failed to disable the schedule task.")
                    return

        if old_task_name and old_task_name != new_task_name and self.scheduler_manager.task_exists(old_task_name):
            self.scheduler_manager.remove_reminder(old_task_name)

        job_data = existing_job.copy()
        job_data["schedule"] = schedule

        if not self.config_manager.update_job(job_index, job_data):
            messagebox.showerror("Schedule", "Failed to save schedule to config.")
            return

        self._refresh_settings_file_status()
        self.lbl_schedule_status.config(text=f"Schedule saved for job: {job_name}")
        messagebox.showinfo("Schedule", "Schedule saved successfully.")

    def _remove_job_schedule(self):
        job_name = self.combo_schedule_job.get()
        if not job_name:
            messagebox.showwarning("Schedule", "Select a job first.")
            return

        job_index, existing_job = self._get_job_by_name(job_name)
        if existing_job is None:
            messagebox.showerror("Schedule", "Selected job no longer exists.")
            self._refresh_schedule_jobs()
            return

        schedule = existing_job.get("schedule") or {}
        task_name = (schedule.get("task_name") or self._default_task_name_for_job(job_name)).strip()

        if task_name and self.scheduler_manager.task_exists(task_name):
            if not self.scheduler_manager.remove_reminder(task_name):
                messagebox.showerror("Schedule", "Failed to remove task from Windows Scheduler.")
                return

        job_data = existing_job.copy()
        job_data["schedule"] = self._default_job_schedule(job_name)

        if not self.config_manager.update_job(job_index, job_data):
            messagebox.showerror("Schedule", "Failed to update config while removing schedule.")
            return

        self._refresh_settings_file_status()
        self._on_schedule_job_selected()
        self.lbl_schedule_status.config(text=f"Schedule removed for job: {job_name}")
        messagebox.showinfo("Schedule", "Schedule removed.")

    # ------------------------------------------------------------------
    # Auto-update
    # ------------------------------------------------------------------

    def _auto_check_updates(self):
        """Silent background update check on startup. Prompts only if an update exists."""
        try:
            updater = Updater()
            result = updater.check_for_update(__version__)
            if result:
                latest, url = result
                self.after(0, lambda: self._prompt_update(latest, url))
        except Exception:
            pass  # Never let a failed update check disrupt startup

    def _check_for_updates(self):
        """Manual update check from the Settings button (gives feedback either way)."""
        self.lbl_update_status.config(text="Checking for updates...")
        threading.Thread(target=self._check_for_updates_thread, daemon=True).start()

    def _check_for_updates_thread(self):
        updater = Updater()
        result = updater.check_for_update(__version__)
        if result:
            latest, url = result
            self.after(0, lambda: self.lbl_update_status.config(text=f"Update available: v{latest}"))
            self.after(0, lambda: self._prompt_update(latest, url))
        else:
            self.after(0, lambda: self.lbl_update_status.config(
                text=f"Version {__version__} — up to date."))
            self.after(0, lambda: messagebox.showinfo(
                "Updates", f"You are running the latest version ({__version__})."))

    def _prompt_update(self, latest_version, download_url):
        if not getattr(sys, 'frozen', False):
            messagebox.showinfo(
                "Update Available",
                f"Version {latest_version} is available.\n\n"
                "Auto-update only works in the packaged app. "
                "Please pull the latest code in development mode."
            )
            return

        proceed = messagebox.askyesno(
            "Update Available",
            f"A new version ({latest_version}) is available.\n"
            f"You are running {__version__}.\n\n"
            "Download and install now? The app will restart automatically.\n"
            "(Your settings and backup history are preserved.)"
        )
        if proceed:
            threading.Thread(target=self._download_and_apply, args=(download_url,), daemon=True).start()

    def _download_and_apply(self, url):
        updater = Updater()

        def progress(done, total, msg):
            self.after(0, lambda: self.lbl_update_status.config(text=msg))

        zip_path = updater.download_update(url, progress_callback=progress)
        if not zip_path:
            self.after(0, lambda: messagebox.showerror(
                "Update Failed", "Could not download the update. Check logs and your connection."))
            self.after(0, lambda: self.lbl_update_status.config(text="Update download failed."))
            return

        self.after(0, lambda: self.lbl_update_status.config(text="Installing update..."))
        if updater.apply_update(zip_path):
            self.after(0, lambda: messagebox.showinfo(
                "Updating", "The update is being installed. The app will now close and restart."))
            self.after(500, self.destroy)
        else:
            self.after(0, lambda: messagebox.showerror(
                "Update Failed", "Could not apply the update. Check logs."))
            self.after(0, lambda: self.lbl_update_status.config(text="Update install failed."))
