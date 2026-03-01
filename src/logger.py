import logging
import logging.handlers
import os
import sys

def setup_logger(log_level=logging.INFO, log_dir="logs"):
    """
    Sets up a logger with both console and file handlers.
    """
    # Create logs directory if it doesn't exist
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    log_file = os.path.join(log_dir, "backup_utility.log")

    logger = logging.getLogger('backup_logger')
    logger.setLevel(log_level)

    # Prevent multiple handlers being added if setup is called multiple times
    if not logger.handlers:
        # Create console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

        # Create file handler
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=5*1024*1024, backupCount=3
        )
        file_handler.setLevel(log_level)
        file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger

def get_logger():
    """
    Convenience function to get the logger.
    """
    return logging.getLogger('backup_logger')
