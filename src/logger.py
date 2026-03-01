import logging
import logging.handlers
import os
import sys

def setup_logger(log_level=logging.INFO, log_dir="logs"):
    """
    Sets up a logger with both console and file handlers.
    """
    # Resolve log directory relative to the application root.
    if getattr(sys, 'frozen', False):
        app_root = os.path.dirname(sys.executable)
    else:
        app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    resolved_log_dir = log_dir
    if not os.path.isabs(resolved_log_dir):
        resolved_log_dir = os.path.join(app_root, resolved_log_dir)

    if not os.path.exists(resolved_log_dir):
        os.makedirs(resolved_log_dir)

    log_file = os.path.join(resolved_log_dir, "backup_utility.log")

    # Configure root logger so all module loggers (logging.getLogger(__name__))
    # are captured by the same handlers.
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    existing_file_handler = None
    existing_console_handler = None
    for handler in root_logger.handlers:
        if isinstance(handler, logging.handlers.RotatingFileHandler):
            existing_file_handler = handler
        elif isinstance(handler, logging.StreamHandler) and getattr(handler, "stream", None) is sys.stdout:
            existing_console_handler = handler

    if not existing_console_handler:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)s | %(name)s | %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

    if not existing_file_handler:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding='utf-8'
        )
        file_handler.setLevel(log_level)
        file_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)s | %(name)s | %(threadName)s | %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    app_logger = logging.getLogger('backup_logger')
    app_logger.setLevel(log_level)
    app_logger.propagate = True

    app_logger.info("Logger initialized. Log file: %s", log_file)
    return app_logger

def get_logger():
    """
    Convenience function to get the logger.
    """
    return logging.getLogger('backup_logger')
