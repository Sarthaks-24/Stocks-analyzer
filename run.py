# run_all.py (Watchdog Edition with Environment Fix)
import sys
import os  # <-- Make sure 'os' is imported
import time
import logging
import subprocess
import datetime
import pytz  # For timezone handling
from apscheduler.schedulers.blocking import BlockingScheduler

# --- Configuration ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON_EXECUTABLE = sys.executable
LOG_DIR = os.path.join(BASE_DIR, "logs")
MANAGER_LOG = os.path.join(LOG_DIR, "manager.log")
FETCH_LOG = os.path.join(LOG_DIR, "fetch_data.log")
DASHBOARD_LOG = os.path.join(LOG_DIR, "dashboard.log")

# Define the Indian timezone
INDIAN_TIMEZONE = pytz.timezone("Asia/Kolkata")

# --- Global State Variables ---
fetch_process = None
dashboard_process = None
last_run_a_token = None   # Will store the date, e.g., 2025-11-03
last_run_req_token = None # Will store the date

# --- Setup Logging ---
os.makedirs(LOG_DIR, exist_ok=True) 
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(MANAGER_LOG),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger('manager')


# --- Functions to Run Your Scripts ---

def run_a_token():
    """Runs a_token_req.py and updates global state on success."""
    global last_run_a_token
    log.info("JOB: Attempting to run 'a_token_req.py'...")
    try:
        result = subprocess.run(
            [PYTHON_EXECUTABLE, "a_token_req.py"],
            cwd=BASE_DIR, capture_output=True, text=True, check=True,
            encoding='utf-8', # Fix for unicode (emoji) errors
            env=os.environ      # <-- THE FIX: Inherit environment variables
        )
        log.info(f"'a_token_req.py' succeeded:\n{result.stdout}")
        last_run_a_token = datetime.datetime.now(INDIAN_TIMEZONE).date()
    except subprocess.CalledProcessError as e:
        log.error(f"'a_token_req.py' FAILED:\n{e.stderr}")
    except Exception as e:
        log.error(f"Error running 'a_token_req.py': {e}")

# In run_all.py

def run_req_token():
    """Runs req_token.py and updates global state on success."""
    global last_run_req_token
    log.info("JOB: Attempting to run 'req_token.py'...")
    try:
        result = subprocess.run(
            [PYTHON_EXECUTABLE, "req_token.py"],
            cwd=BASE_DIR, capture_output=True, text=True, check=True,
            encoding='utf-8',  # <-- THIS IS THE FIX
            env=os.environ      
        )
        log.info(f"'req_token.py' succeeded:\n{result.stdout}")
        last_run_req_token = datetime.datetime.now(INDIAN_TIMEZONE).date()
    except subprocess.CalledProcessError as e:
        log.error(f"'req_token.py' FAILED:\n{e.stderr}")
    except Exception as e:
        log.error(f"Error running 'req_token.py': {e}")

def start_market_scripts():
    """
    Starts fetch_data.py and dashboard.py IF THEY ARE NOT ALREADY RUNNING.
    """
    global fetch_process, dashboard_process
    
    # Check fetch_data.py
    if fetch_process is None or fetch_process.poll() is not None:
        log.info("JOB: 'fetch_data.py' is not running. Starting...")
        try:
            fetch_logfile = open(FETCH_LOG, 'a')
            fetch_process = subprocess.Popen(
                [PYTHON_EXECUTABLE, "fetch_data.py"],
                cwd=BASE_DIR, stdout=fetch_logfile, stderr=subprocess.STDOUT,
                env=os.environ  # <-- THE FIX: Also needed for fetch_data's API call
            )
            log.info(f"'fetch_data.py' started with PID: {fetch_process.pid}")
        except Exception as e:
            log.error(f"Failed to start 'fetch_data.py': {e}")
    else:
        log.debug(f"'fetch_data.py' is already running (PID: {fetch_process.pid}).")

    # Check dashboard.py
    if dashboard_process is None or dashboard_process.poll() is not None:
        log.info("JOB: 'dashboard.py' is not running. Starting...")
        try:
            dash_logfile = open(DASHBOARD_LOG, 'a')
            dashboard_process = subprocess.Popen(
                [PYTHON_EXECUTABLE, "dashboard.py"],
                cwd=BASE_DIR, stdout=dash_logfile, stderr=subprocess.STDOUT,
                env=os.environ  # <-- THE FIX: Good practice to include it here too
            )
            log.info(f"'dashboard.py' started with PID: {dashboard_process.pid}")
        except Exception as e:
            log.error(f"Failed to start 'dashboard.py': {e}")
    else:
        log.debug(f"'dashboard.py' is already running (PID: {dashboard_process.pid}).")


def stop_market_scripts():
    """
    Stops fetch_data.py and dashboard.py IF THEY ARE RUNNING.
    """
    global fetch_process, dashboard_process
    
    if fetch_process and fetch_process.poll() is None:
        log.info(f"JOB: Stopping 'fetch_data.py' (PID: {fetch_process.pid})...")
        try:
            fetch_process.terminate()
            fetch_process.wait(timeout=5)
            log.info("'fetch_data.py' terminated.")
        except subprocess.TimeoutExpired:
            log.warning(f"'fetch_data.py' did not terminate, killing...")
            fetch_process.kill()
        except Exception as e:
            log.error(f"Error stopping 'fetch_data.py': {e}")
        finally:
            fetch_process = None
    else:
        fetch_process = None # Ensure it's marked as None if process is dead

    if dashboard_process and dashboard_process.poll() is None:
        log.info(f"JOB: Stopping 'dashboard.py' (PID: {dashboard_process.pid})...")
        try:
            dashboard_process.terminate()
            dashboard_process.wait(timeout=5)
            log.info("'dashboard.py' terminated.")
        except subprocess.TimeoutExpired:
            log.warning(f"'dashboard.py' did not terminate, killing...")
            dashboard_process.kill()
        except Exception as e:
            log.error(f"Error stopping 'dashboard.py': {e}")
        finally:
            dashboard_process = None
    else:
        dashboard_process = None


# --- The Main Watchdog Function ---

def watchdog_check():
    """
    This is the main "brain" of the scheduler.
    It runs every 5 minutes and checks what *should* be running.
    """
    global last_run_a_token, last_run_req_token
    
    try:
        # Get current date and time in India
        now = datetime.datetime.now(INDIAN_TIMEZONE)
        today = now.date()
        current_time = now.time()
        day_of_week = now.weekday() # 0=Monday, 6=Sunday

        log.info(f"--- Watchdog Check --- Today: {today}, Time: {current_time}, Day: {day_of_week}")

        # --- Rule 1: Check for Weekends ---
        if day_of_week >= 5: # 5=Saturday, 6=Sunday
            log.info("Watchdog: Weekend. Ensuring market scripts are stopped.")
            stop_market_scripts()
            last_run_a_token = None
            last_run_req_token = None
            return

        # --- Rule 2: Check `a_token_req.py` ---
        if current_time >= datetime.time(5, 0) and last_run_a_token != today:
            log.info("Watchdog: 'a_token' needs to run.")
            run_a_token()

        # --- Rule 3: Check `req_token.py` ---
        if current_time >= datetime.time(8, 45) and last_run_req_token != today:
            log.info("Watchdog: 'req_token' needs to run.")
            run_req_token()

        # --- Rule 4: Check Market Scripts (fetch_data & dashboard) ---
        market_open = datetime.time(9, 15)
        market_close = datetime.time(15, 31) # 3:31 PM

        if market_open <= current_time < market_close:
            log.info("Watchdog: Market is OPEN. Ensuring scripts are running.")
            start_market_scripts()
        else:
            log.info("Watchdog: Market is CLOSED. Ensuring scripts are stopped.")
            stop_market_scripts()

    except Exception as e:
        log.error(f"FATAL ERROR in watchdog_check loop: {e}", exc_info=True)


# --- Main Scheduler Execution ---
if __name__ == "__main__":
    log.info("--- Starting Automation Manager (Watchdog Mode) ---")
    
    scheduler = BlockingScheduler(timezone=INDIAN_TIMEZONE)
    scheduler.add_job(watchdog_check, 'interval', minutes=5, id="watchdog")
    
    log.info("Scheduler configured with 5-minute watchdog interval.")
    log.info(f"Using Python: {PYTHON_EXECUTABLE}")

    log.info("Running initial watchdog check on startup...")
    watchdog_check()
    log.info("Initial check complete. Handing over to scheduler.")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("--- Automation Manager Shutting Down ---")
        stop_market_scripts()
        log.info("Shutdown complete.")