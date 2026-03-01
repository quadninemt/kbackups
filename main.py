import sys
import os
import tkinter as tk
from tkinter import messagebox
from src.config_manager import ConfigManager
from src.gui.main_window import MainWindow
from src.logger import setup_logger

def main():
    logger = setup_logger()
    logger.info("Starting k_backups Utility...")
    
    try:
        config_manager = ConfigManager()
        app = MainWindow(config_manager)
        app.mainloop()
    except Exception as e:
        logger.critical(f"Application crash: {e}", exc_info=True)
        # Maybe show error dialog if tk is available
        try:
            messagebox.showerror("Critical Error", f"Application crashed: {e}")
        except:
            print(f"Failed to show messagebox: {e}")

if __name__ == "__main__":
    main()
