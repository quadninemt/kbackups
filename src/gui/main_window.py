import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import threading
from src.config_manager import ConfigManager
from src.scheduler_manager import SchedulerManager

class MainWindow(tk.Tk):
    def __init__(self, config_manager):
        super().__init__()
        self.config_manager = config_manager
        self.scheduler_manager = SchedulerManager()
        
        self.title("k_backups - Backup Utility")
        self.geometry("800x600")
        
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
            # Customize colors for dark mode manually if theme missing
            style.configure(".", background="#333", foreground="#EEE")
            style.configure("TLabel", background="#333", foreground="#EEE")
            style.configure("TButton", background="#555", foreground="#EEE")
            self.configure(bg="#333")

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
        frame_actions.pack(pady=20)
        
        self.btn_backup = ttk.Button(frame_actions, text="Backup Now", command=self._start_backup)
        self.btn_backup.pack(side=tk.LEFT, padx=10)
        
        # Progress
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.tab_dashboard, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, padx=20, pady=10)
        
        self.lbl_status = ttk.Label(self.tab_dashboard, text="Ready")
        self.lbl_status.pack(pady=5)

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
        # Simple prompt for new job name
        # Ideally a full dialog, but for now simple steps
        # Use simpledialog logic or custom implementation
        top = tk.Toplevel(self)
        top.title("Add New Job")
        top.geometry("400x300")
        
        ttk.Label(top, text="Job Name:").pack(pady=5)
        ent_name = ttk.Entry(top)
        ent_name.pack(pady=5)
        
        ttk.Label(top, text="Source Folder:").pack(pady=5)
        ent_source = ttk.Entry(top)
        ent_source.pack(pady=5)
        def browse_source():
            d = filedialog.askdirectory()
            if d:
                ent_name.delete(0, tk.END)
                ent_name.insert(0, d) # Wait, did I map source to name? No.
                ent_source.delete(0, tk.END)
                ent_source.insert(0, d)
        ttk.Button(top, text="Browse...", command=browse_source).pack(pady=2)

        ttk.Label(top, text="Destination Folder (on NAS):").pack(pady=5)
        ent_dest = ttk.Entry(top)
        ent_dest.pack(pady=5)
        
        def save():
            name = ent_name.get()
            src = ent_source.get()
            dest = ent_dest.get()
            
            if not name or not src:
                messagebox.showwarning("Error", "Name and Source are required.")
                return
                
            job_data = {
                "name": name,
                "source_paths": [src],
                "destination_path": dest,
                "exclude_patterns": []
            }
            self.config_manager.add_job(job_data)
            self._refresh_all_job_lists()
            top.destroy()
            
        ttk.Button(top, text="Save Job", command=save).pack(pady=20)

    def _delete_job(self):
        selected = self.tree_jobs.selection()
        if not selected:
            return
        idx = int(selected[0])
        if messagebox.askyesno("Confirm", "Delete selected job?"):
            self.config_manager.delete_job(idx)
            self._refresh_all_job_lists()

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

        # Scheduler
        frame_scheduler = ttk.LabelFrame(self.tab_settings, text="Schedule")
        frame_scheduler.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(frame_scheduler, text="Enable Monthly Reminder", command=self._enable_reminder).pack(side=tk.LEFT, padx=10, pady=10)
        ttk.Button(frame_scheduler, text="Remove Reminder", command=self._remove_reminder).pack(side=tk.LEFT, padx=10, pady=10)
        
        # Load existing
        nas_config = self.config_manager.get_nas_settings()
        self.ent_nas_address.insert(0, nas_config.get("address", ""))
        self.ent_nas_user.insert(0, nas_config.get("username", ""))
        self.ent_nas_pass.insert(0, nas_config.get("password", ""))

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
        messagebox.showinfo("Saved", "NAS settings saved successfully.")

    def _refresh_all_job_lists(self):
        self._refresh_jobs_list()
        self._refresh_jobs_tree()
        self._refresh_restore_jobs()

    def _refresh_jobs_list(self):
        jobs = self.config_manager.get_jobs()
        job_names = [j['name'] for j in jobs]
        self.combo_jobs['values'] = job_names
        if job_names and not self.combo_jobs.get():
            self.combo_jobs.current(0)

    def _refresh_restore_jobs(self):
        jobs = self.config_manager.get_jobs()
        names = [j['name'] for j in jobs]
        if hasattr(self, 'combo_restore_jobs'):
             self.combo_restore_jobs['values'] = names
             if names and not self.combo_restore_jobs.get():
                 self.combo_restore_jobs.current(0)

    def _start_backup(self):
        job_name = self.combo_jobs.get()
        if not job_name:
            messagebox.showwarning("Warning", "Please select a job first.")
            return

        self.btn_backup.state(['disabled'])
        self.lbl_status.config(text="Starting backup...")
        self.progress_var.set(0)
        
        # Run in thread
        threading.Thread(target=self._run_backup_thread, args=(job_name,), daemon=True).start()

    def _run_backup_thread(self, job_name):
        engine = BackupEngine(self.config_manager)
        
        def progress_callback(processed, total, msg):
            # Update UI from thread safely
            if total > 0:
                pct = (processed / total) * 100
                self.after(0, lambda: self.progress_var.set(pct))
            self.after(0, lambda: self.lbl_status.config(text=msg))

        success = engine.run_job(job_name, progress_callback)
        
        self.after(0, lambda: self.btn_backup.state(['!disabled']))
        if success:
            self.after(0, lambda: messagebox.showinfo("Backup", "Backup completed successfully!"))
        else:
            self.after(0, lambda: messagebox.showerror("Backup", "Backup failed. Check logs."))

    def _enable_reminder(self):
        # We need to know the executable path. sys.executable usually handles pyinstaller exe.
        import sys
        
        task_name = "k_backups_monthly"
        executable = sys.executable
        if not getattr(sys, 'frozen', False):
            # Development mode: python gui script?
            # Or just pass python executable
            pass
            
        success = self.scheduler_manager.create_monthly_reminder(task_name)
        if success:
            messagebox.showinfo("Schedule", "Monthly reminder enabled.")
        else:
            messagebox.showerror("Schedule", "Failed to create task (Check logs/Run as Admin).")

    def _remove_reminder(self):
        task_name = "k_backups_monthly"
        success = self.scheduler_manager.remove_reminder(task_name)
        if success:
            messagebox.showinfo("Schedule", "Reminder removed.")
        else:
            messagebox.showerror("Schedule", "Failed to remove task.")
