# storage.py
import json
import os
import logging
from typing import Dict, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STORAGE_FILE = "user_program.json"

# Initialize user_program dictionary
user_program: Dict[str, Dict[str, List[str]]] = {}

# Load data at startup
try:
    if os.path.exists(STORAGE_FILE):
        with open(STORAGE_FILE, "r", encoding="utf-8") as f:
            user_program = json.load(f)
            # Ensure keys are strings
            user_program = {str(k): v for k, v in user_program.items()}
            logger.info(f"Loaded user_program from {STORAGE_FILE}: {len(user_program)} users")
    else:
        logger.warning(f"File {STORAGE_FILE} does not exist. Starting with empty user_program.")
except json.JSONDecodeError as e:
    logger.error(f"Failed to parse {STORAGE_FILE}: {e}. Starting with empty user_program.")
    user_program = {}
except Exception as e:
    logger.error(f"Error loading {STORAGE_FILE}: {e}. Starting with empty user_program.")
    user_program = {}

def save_user_program():
    """Save user_program to file."""
    try:
        logger.debug(f"Saving user_program: {user_program}")
        with open(STORAGE_FILE, "w", encoding="utf-8") as f:
            json.dump(user_program, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved user_program to {STORAGE_FILE}: {len(user_program)} users")
    except Exception as e:
        logger.error(f"Error saving {STORAGE_FILE}: {e}")

def count_programs() -> int:
    """Count the total number of training programs created."""
    count = len(user_program)
    logger.debug(f"Counted {count} programs in user_program")
    return count