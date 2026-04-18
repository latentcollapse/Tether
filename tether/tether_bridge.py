#!/usr/bin/env python3
"""
Tether Bridge — Watchdog for HLX Job Board.
Automatically closes Tether messages when tickets are completed/cancelled.
"""
import time
import os
import sys
import tomllib
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Ensure we can import tether
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from tether import SQLiteRuntime
except ImportError:
    # Try parent dir if running from a different context
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from tether import SQLiteRuntime

# Paths
JOB_BOARD_PATH = "/mnt/d/Language Projects/hlx-workspace/HLX/HLX_JOB_BOARD.toml"
# Use TETHER_DB env var or default logic
_default_db = "/mnt/d/Language Projects/Tether/postoffice.db"
DB_PATH = os.environ.get("TETHER_DB", _default_db)

class JobBoardHandler(FileSystemEventHandler):
    def __init__(self, runtime: SQLiteRuntime):
        self.runtime = runtime
        self.last_snapshot = self._load_snapshot()
        self.last_run = 0

    def _load_snapshot(self):
        try:
            if not os.path.exists(JOB_BOARD_PATH):
                return {}
            with open(JOB_BOARD_PATH, "rb") as f:
                data = tomllib.load(f)
                return {t["id"]: t["status"] for t in data.get("ticket", [])}
        except Exception as e:
            print(f"Error loading job board: {e}")
            return {}

    def on_modified(self, event):
        # Watchdog might fire for the directory or the file
        if event.src_path == str(JOB_BOARD_PATH) or os.path.basename(event.src_path) == "HLX_JOB_BOARD.toml":
            # Debounce rapid saves (500ms)
            now = time.time()
            if now - self.last_run < 0.5:
                return
            self.last_run = now
            
            # Wait a beat for the write to stabilize
            time.sleep(0.2)
            
            current_snapshot = self._load_snapshot()
            if not current_snapshot:
                return

            for tid, status in current_snapshot.items():
                old_status = self.last_snapshot.get(tid)
                if status != old_status:
                    print(f"[{time.strftime('%H:%M:%S')}] Ticket {tid} transitioned: {old_status} -> {status}")
                    if status in ("complete", "cancelled"):
                        tether_status = "completed" if status == "complete" else "cancelled"
                        print(f"  -> Closing associated Tether messages as '{tether_status}'")
                        self.runtime.close_handle(ticket_id=tid, status=tether_status)
            
            self.last_snapshot = current_snapshot

def main():
    if not os.path.exists(JOB_BOARD_PATH):
        print(f"Error: Job board not found at {JOB_BOARD_PATH}")
        sys.exit(1)

    print(f"Tether Bridge starting...")
    print(f"Watching: {JOB_BOARD_PATH}")
    print(f"Database: {DB_PATH}")
    sys.stdout.flush()
    
    runtime = SQLiteRuntime(DB_PATH)
    event_handler = JobBoardHandler(runtime)
    observer = Observer()
    # Watch the directory, but handler filters for the specific file
    observer.schedule(event_handler, path=os.path.dirname(JOB_BOARD_PATH), recursive=False)
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    main()
