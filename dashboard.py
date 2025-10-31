import json
import os
import glob
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime, timedelta, time as dt_time  # <-- Make sure dt_time is imported
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.dates import DateFormatter
import matplotlib.ticker as ticker
from tkcalendar import DateEntry
import threading
import time
import re
import sqlite3

# --- Constants ---
DB_FILE = "resources/live_data.db"
RESOURCES_DIR = "resources"
REFRESH_RATE_MS = 2000
MARKET_CLOSE_TIME = dt_time(15, 30, 0) # 3:30 PM

# --- Main Application Class ---
class OptionChainDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("Option Chain Dashboard (SQLite Edition)")
        self.root.geometry("2000x800")

        self.chain_file_var = tk.StringVar()
        self.chain_data = {}
        self.instrument_map = {}
        self.current_expiry_date = None
        self.latest_snapshot_date = None
        
        self.date_change_timer = None
        self.update_in_progress = False
        self.debug_mode = True
        
        self.setup_gui()
        self.load_available_chains()
        self.auto_refresh_data()

    def log_debug(self, message):
        """Print debug messages."""
        if self.debug_mode:
            print(f"[DEBUG] {message}")

    def safe_get_nested(self, data, *keys, default=None):
        """
        Safely navigate nested dictionary structure.
        """
        result = data
        for key in keys:
            if isinstance(result, dict):
                result = result.get(key)
                if result is None:
                    return default
            else:
                return default
        return result if result is not None else default

    def setup_gui(self):
        """Creates the main GUI layout."""
        top_frame = ttk.Frame(self.root, padding="10")
        top_frame.pack(fill=tk.X)
        
        # Chain selector
        ttk.Label(top_frame, text="Select Option Chain:").pack(side=tk.LEFT, padx=(0, 5))
        self.chain_dropdown = ttk.Combobox(
            top_frame, textvariable=self.chain_file_var, state="readonly", width=40
        )
        self.chain_dropdown.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.chain_dropdown.bind("<<ComboboxSelected>>", self.on_chain_select)
        
        # Date Range selector
        date_frame = ttk.LabelFrame(top_frame, text="Date Range", padding="5")
        date_frame.pack(side=tk.LEFT, padx=10, fill=tk.Y)

        # Start date
        start_frame = ttk.Frame(date_frame)
        start_frame.pack(side=tk.LEFT, padx=5)
        ttk.Label(start_frame, text="From:").pack(side=tk.TOP)
        self.start_date = DateEntry(
            start_frame,
            width=12,
            background='darkblue',
            foreground='white',
            borderwidth=2,
            date_pattern='yyyy-mm-dd',
            firstweekday='sunday'
        )
        self.start_date.pack(side=tk.TOP, pady=2)
        self.start_date.set_date(datetime.now().date())
        self.start_date.bind("<<DateEntrySelected>>", self.on_date_change)

        # End date
        end_frame = ttk.Frame(date_frame)
        end_frame.pack(side=tk.LEFT, padx=5)
        ttk.Label(end_frame, text="To:").pack(side=tk.TOP)
        self.end_date = DateEntry(
            end_frame,
            width=12,
            background='darkblue',
            foreground='white',
            borderwidth=2,
            date_pattern='yyyy-mm-dd',
            firstweekday='sunday'
        )
        self.end_date.pack(side=tk.TOP, pady=2)
        self.end_date.set_date(datetime.now().date())
        self.end_date.bind("<<DateEntrySelected>>", self.on_date_change)
        
        # Refresh button
        self.refresh_button = ttk.Button(
            top_frame, text="Refresh Now", command=self.force_refresh
        )
        self.refresh_button.pack(side=tk.LEFT, padx=10)

        # --- Bottom Status Frame ---
        bottom_frame = ttk.Frame(self.root, padding="10")
        bottom_frame.pack(fill=tk.X, side=tk.BOTTOM)

        # Status label
        self.status_label = ttk.Label(bottom_frame, text="", foreground="gray")
        self.status_label.pack(side=tk.LEFT, padx=10)

        # Debug button
        self.debug_button = ttk.Button(
            bottom_frame, text="Debug Info", command=self.show_debug_info
        )
        self.debug_button.pack(side=tk.RIGHT, padx=5)
        
        # --- Tree setup ---
        tree_frame = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        tree_frame.pack(fill=tk.BOTH, expand=True)

        columns = (
            "call_oi_chg_pct", "call_oi", "call_ltp", 
            "call_iv", "call_delta", "call_gamma", "call_vega", "call_theta", 
            "strike", 
            "put_theta", "put_vega", "put_gamma", "put_delta", "put_iv", 
            "put_ltp", "put_oi", "put_oi_chg_pct"
        )
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings")
        
        # Define Headings
        self.tree.heading("call_oi_chg_pct", text="Chg %") 
        self.tree.heading("call_oi", text="Call OI")
        self.tree.heading("call_ltp", text="Call LTP")
        self.tree.heading("call_iv", text="IV") 
        self.tree.heading("call_delta", text="Delta") 
        self.tree.heading("call_gamma", text="Gamma") 
        self.tree.heading("call_vega", text="Vega") 
        self.tree.heading("call_theta", text="Theta") 
        self.tree.heading("strike", text="Strike")
        self.tree.heading("put_theta", text="Theta") 
        self.tree.heading("put_vega", text="Vega") 
        self.tree.heading("put_gamma", text="Gamma") 
        self.tree.heading("put_delta", text="Delta") 
        self.tree.heading("put_iv", text="IV") 
        self.tree.heading("put_ltp", text="Put LTP")
        self.tree.heading("put_oi", text="Put OI")
        self.tree.heading("put_oi_chg_pct", text="Chg %") 

        # Define Column properties
        col_width, greek_width = 80, 70
        for col in ["call_oi_chg_pct", "call_oi", "call_ltp"]:
            self.tree.column(col, width=col_width, anchor=tk.E)
        for col in ["call_iv", "call_delta", "call_gamma", "call_vega", "call_theta"]:
            self.tree.column(col, width=greek_width, anchor=tk.E)
        self.tree.column("strike", width=80, anchor=tk.CENTER)
        for col in ["put_theta", "put_vega", "put_gamma", "put_delta", "put_iv"]:
            self.tree.column(col, width=greek_width, anchor=tk.W)
        for col in ["put_ltp", "put_oi", "put_oi_chg_pct"]:
            self.tree.column(col, width=col_width, anchor=tk.W)

        style = ttk.Style()
        style.configure("Treeview", rowheight=28, font=('Helvetica', 9))
        style.configure("Treeview.Heading", font=('Helvetica', 9, 'bold'))
        self.tree.tag_configure("oddrow", background="#FAFAFA")
        self.tree.tag_configure("evenrow", background="#FFFFFF")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side='right', fill='y')
        hsb.pack(side='bottom', fill='x')
        self.tree.pack(side='left', fill='both', expand=True)
        self.tree.bind("<Button-3>", self.show_context_menu)

    def show_debug_info(self):
        """Show debug information dialog."""
        debug_info = []
        debug_info.append(f"Chain File: {self.chain_file_var.get()}")
        debug_info.append(f"Selected Expiry: {self.current_expiry_date}")
        debug_info.append(f"Date Range: {self.start_date.get_date()} to {self.end_date.get_date()}")
        debug_info.append(f"Displaying Snapshot For: {self.latest_snapshot_date}")
        debug_info.append(f"Total Strikes: {len(self.chain_data)}")
        debug_info.append(f"Instrument Map Size: {len(self.instrument_map)}")
        debug_info.append(f"Database File: {DB_FILE} (Exists: {os.path.exists(DB_FILE)})")
        if os.path.exists(DB_FILE):
             debug_info.append(f"Database Size: {os.path.getsize(DB_FILE) / (1024*1024):.2f} MB")
        
        messagebox.showinfo("Debug Information", "\n".join(debug_info))

    def on_date_change(self, event=None):
        """Debounced date change handler."""
        if self.date_change_timer:
            self.root.after_cancel(self.date_change_timer)
        self.date_change_timer = self.root.after(500, self.force_refresh)

    def force_refresh(self):
        """Force refresh by clearing cache and updating."""
        self.log_debug("Force refresh initiated")
        self.update_all_rows()

    def load_available_chains(self):
        """Load available chain files."""
        try:
            search_pattern = os.path.join(RESOURCES_DIR, "*-*-*.json")
            chain_files = [os.path.basename(f) for f in glob.glob(search_pattern)]
            self.log_debug(f"Found {len(chain_files)} chain files")
            
            if not chain_files:
                messagebox.showwarning("No Chains", f"No option chain files (*-*-*.json) found in '{RESOURCES_DIR}'.\nPlease run `search.py` first.")
                return
            
            self.chain_dropdown['values'] = sorted(chain_files)
            if chain_files:
                self.chain_dropdown.set(chain_files[0])
                self.on_chain_select()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to scan resources dir: {e}")

    def on_chain_select(self, event=None):
        """Handle chain selection."""
        filename = self.chain_file_var.get()
        if not filename: 
            return
        
        filepath = os.path.join(RESOURCES_DIR, filename)
        self.log_debug(f"Loading chain file: {filepath}")

        # --- DYNAMIC DATE LOGIC ---
        self.current_expiry_date = None
        match = re.search(r'(\d{2}-\d{2}-\d{4})\.json$', filename)
        if match:
            try:
                self.current_expiry_date = datetime.strptime(match.group(1), '%d-%m-%Y').date()
                self.log_debug(f"Parsed expiry date: {self.current_expiry_date}")
            except ValueError as e:
                self.log_debug(f"Could not parse date from filename: {e}")
        
        # Configure date pickers based on expiry
        today = datetime.now().date()
        if self.current_expiry_date:
            # Set max date for calendars to the expiry date
            self.start_date.config(maxdate=self.current_expiry_date)
            self.end_date.config(maxdate=self.current_expiry_date)
            
            # Set end_date to expiry or today, whichever is earlier
            default_end_date = min(self.current_expiry_date, today)
            self.end_date.set_date(default_end_date)
            self.start_date.set_date(default_end_date) # Also set start date
        else:
            # Reset if no valid expiry found
            self.start_date.config(maxdate=None)
            self.end_date.config(maxdate=None)
            self.end_date.set_date(today)
            self.start_date.set_date(today)
        # --- END DYNAMIC DATE LOGIC ---

        try:
            with open(filepath, 'r') as f: 
                self.chain_data = json.load(f)
            
            self.log_debug(f"Loaded {len(self.chain_data)} strikes from chain file")
            self.populate_tree_skeleton()
            self.update_all_rows()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load chain '{filename}': {e}")
            self.chain_data, self.instrument_map = {}, {}

    def populate_tree_skeleton(self):
        """Create tree structure with strikes."""
        for item in self.tree.get_children(): 
            self.tree.delete(item)
        self.instrument_map.clear()
        
        if not self.chain_data: 
            return

        try: 
            sorted_strikes = sorted(self.chain_data.keys(), key=float)
        except ValueError: 
            sorted_strikes = sorted(self.chain_data.keys())

        self.log_debug(f"Populating tree with {len(sorted_strikes)} strikes")
        
        num_placeholders = len(self.tree['columns'])
        placeholders = [""] * num_placeholders
        strike_col_index = self.tree['columns'].index('strike')

        for i, strike in enumerate(sorted_strikes):
            tags = ("evenrow",) if i % 2 == 0 else ("oddrow",)
            current_placeholders = list(placeholders)
            current_placeholders[strike_col_index] = strike
            item_id = self.tree.insert("", "end", values=current_placeholders, tags=tags)
            
            if "CE" in self.chain_data[strike]:
                ce_key = self.chain_data[strike]["CE"]
                self.instrument_map[ce_key] = (strike, "CE", item_id)
            if "PE" in self.chain_data[strike]:
                pe_key = self.chain_data[strike]["PE"]
                self.instrument_map[pe_key] = (strike, "PE", item_id)

    def auto_refresh_data(self):
        """Auto-refresh timer."""
        try: 
            # Only refresh if "To" date is today
            if self.end_date.get_date() == datetime.now().date():
                if not self.update_in_progress:
                    self.update_all_rows()
        except Exception as e: 
            print(f"Refresh Error: {e}")
        finally: 
            self.root.after(REFRESH_RATE_MS, self.auto_refresh_data)

    def update_all_rows(self):
        """Update all rows using background thread."""
        if not self.instrument_map or self.update_in_progress:
            return
        
        self.update_in_progress = True
        self.status_label.config(text="Updating...")
        self.log_debug("Starting update_all_rows")
        
        threading.Thread(target=self._fetch_and_update, daemon=True).start()

    def _fetch_and_update(self):
        """Background thread to fetch data and schedule UI updates."""
        items_to_update = []
        self.latest_snapshot_date = None
        snapshot_date_str = None
        
        try:
            start_date = self.start_date.get_date()
            end_date = self.end_date.get_date()
            
            # We need to add time to the date to make a full timestamp for the query
            start_timestamp = f"{start_date} 00:00:00"
            end_timestamp = f"{end_date} 23:59:59" 
            
            all_keys = tuple(self.instrument_map.keys())
            if not all_keys:
                self.log_debug("Instrument map is empty, skipping fetch.")
                self.root.after_idle(lambda: self._apply_updates([], no_data_in_range=True))
                return

            # This single, fast query replaces ALL the file reading
            # It finds the latest timestamp for EACH key within the date range
            query = f"""
                SELECT t.timestamp, t.instrument_key, t.ltp, t.cp, t.oi, t.iv, t.delta, t.gamma, t.vega, t.theta 
                FROM ticks t
                INNER JOIN (
                    SELECT instrument_key, MAX(timestamp) AS max_ts
                    FROM ticks
                    WHERE instrument_key IN ({','.join(['?'] * len(all_keys))})
                    AND timestamp BETWEEN ? AND ?
                    GROUP BY instrument_key
                ) tm ON t.instrument_key = tm.instrument_key AND t.timestamp = tm.max_ts
            """
            
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            
            params = all_keys + (start_timestamp, end_timestamp)
            cursor.execute(query, params)
            latest_ticks = cursor.fetchall()
            conn.close()

            if not latest_ticks:
                self.log_debug("No snapshot data found in range.")
                self.root.after_idle(lambda: self._apply_updates([], no_data_in_range=True))
                return

            # Get the snapshot date from the first result for the status bar
            snapshot_date_str = datetime.fromisoformat(latest_ticks[0][0]).strftime('%Y-%m-%d')
            self.latest_snapshot_date = snapshot_date_str

            # Create a dict for fast lookup
            # {instrument_key: (ltp, cp, oi, iv, ...)}
            tick_map = {row[1]: row[2:] for row in latest_ticks}

            for key, (strike, opt_type, item_id) in self.instrument_map.items():
                if key in tick_map:
                    data = tick_map[key]
                    ltp, cp, oi, iv, delta, gamma, vega, theta = data
                    
                    chg_pct = 0.0
                    if cp and cp > 0:
                        chg_pct = ((ltp - cp) / cp) * 100.0
                    
                    if opt_type == "CE":
                        row_data = {
                            "item_id": item_id,
                            "call_ltp": f"{ltp:.2f}",
                            "call_oi": f"{oi:,.0f}",
                            "call_oi_chg_pct": f"{chg_pct:+.1f}%",
                            "call_iv": f"{iv:.2f}",
                            "call_delta": f"{delta:.4f}",
                            "call_gamma": f"{gamma:.4f}",
                            "call_vega": f"{vega:.4f}",
                            "call_theta": f"{theta:.4f}"
                        }
                    else: # PE
                        row_data = {
                            "item_id": item_id,
                            "put_ltp": f"{ltp:.2f}",
                            "put_oi": f"{oi:,.0f}",
                            "put_oi_chg_pct": f"{chg_pct:+.1f}%",
                            "put_iv": f"{iv:.2f}",
                            "put_delta": f"{delta:.4f}",
                            "put_gamma": f"{gamma:.4f}",
                            "put_vega": f"{vega:.4f}",
                            "put_theta": f"{theta:.4f}"
                        }
                    items_to_update.append(row_data)

            self.log_debug(f"Found {len(latest_ticks)} ticks. Rows to update: {len(items_to_update)}")
            
        except Exception as e:
            print(f"Error in _fetch_and_update: {e}")
        finally:
            self.root.after_idle(lambda: self._apply_updates(items_to_update, snapshot_date_str=snapshot_date_str))

    def _apply_updates(self, items_to_update, snapshot_date_str=None, no_data_in_range=False):
        """Apply updates to tree on main thread."""
        try:
            # We must map by item_id since a single row (item_id) gets multiple updates
            updates_by_item = {}
            for row_data in items_to_update:
                item_id = row_data.pop("item_id")
                if item_id not in updates_by_item:
                    updates_by_item[item_id] = {}
                updates_by_item[item_id].update(row_data)

            # Clear all old data first
            for item_id in self.tree.get_children():
                values = self.tree.item(item_id, 'values')
                strike = values[self.tree['columns'].index('strike')]
                new_values = [""] * len(self.tree['columns'])
                new_values[self.tree['columns'].index('strike')] = strike
                self.tree.item(item_id, values=new_values)
            
            # Apply all new updates
            for item_id, updates in updates_by_item.items():
                if self.tree.exists(item_id):
                    for column, value in updates.items():
                        self.tree.set(item_id, column, value)
            
            if no_data_in_range:
                self.status_label.config(text="No data found in selected range.", foreground="red")
            elif items_to_update:
                status_msg = f"Updated {len(updates_by_item)} rows."
                if snapshot_date_str:
                    status_msg += f" (Displaying data for {snapshot_date_str})"
                self.status_label.config(text=status_msg, foreground="green")
            else:
                status_msg = f"No data found"
                if snapshot_date_str:
                    status_msg += f" for date {snapshot_date_str}"
                self.status_label.config(text=status_msg, foreground="red")
        except Exception as e:
            print(f"Error applying updates: {e}")
            self.status_label.config(text="Update failed", foreground="red")
        finally:
            self.update_in_progress = False
            self.root.after(3000, lambda: self.status_label.config(text="", foreground="gray"))

    def get_historical_data(self, instrument_key, data_key_path, minutes):
        """Get historical data points for graphing."""
        start_date = self.start_date.get_date()
        end_date = self.end_date.get_date()
        
        if start_date > end_date:
            messagebox.showerror("Invalid Date Range", f"Start date ({start_date}) must be before or equal to end date ({end_date})")
            return [], "Error"

        # --- FIX: Smarter Time Range Logic ---
        
        # Default: Full day range
        start_ts = f"{start_date} 00:00:00"
        end_ts = f"{end_date} 23:59:59"

        if minutes > 0:
            # We are filtering for the "last X minutes"
            
            # Base the 'end' time on the current time if it's today
            if end_date == datetime.now().date():
                end_datetime = datetime.now()
            else:
                # *** FIX ***
                # For historical, set the 'end' time to the end of the market day
                end_datetime = datetime.combine(end_date, MARKET_CLOSE_TIME)
                # *** END FIX ***

            # Calculate cutoff time X minutes *before* this end_datetime
            cutoff_time = end_datetime - timedelta(minutes=minutes)
            
            # The query range is now from the cutoff to the end time
            start_ts = cutoff_time.isoformat(timespec='microseconds')
            end_ts = end_datetime.isoformat(timespec='microseconds')
        # --- END FIX ---

        # Map the old list-based path to a new column name
        column_map = {
            tuple(["fullFeed", "marketFF", "ltpc", "ltp"]): "ltp",
            tuple(["Chg %"]): "chg_pct", # Special case
            tuple(["fullFeed", "marketFF", "oi"]): "oi",
            tuple(["fullFeed", "marketFF", "iv"]): "iv",
            tuple(["fullFeed", "marketFF", "optionGreeks", "delta"]): "delta",
            tuple(["fullFeed", "marketFF", "optionGreeks", "gamma"]): "gamma",
            tuple(["fullFeed", "marketFF", "optionGreeks", "vega"]): "vega",
            tuple(["fullFeed", "marketFF", "optionGreeks", "theta"]): "theta",
        }
        
        display_key = "Chg %" if data_key_path == ["Chg %"] else ".".join(data_key_path)
        is_chg_pct = (data_key_path == ["Chg %"])
        
        if is_chg_pct:
            query_cols = "timestamp, ltp, cp" # Need ltp and cp to calculate
        else:
            db_col = column_map.get(tuple(data_key_path))
            if not db_col:
                messagebox.showerror("Error", f"Unknown graph key: {display_key}")
                return [], "Error"
            query_cols = f"timestamp, {db_col}"

        query = f"""
            SELECT {query_cols} FROM ticks
            WHERE instrument_key = ?
            AND timestamp BETWEEN ? AND ?
            ORDER BY timestamp
        """
        
        data_points = []
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute(query, (instrument_key, start_ts, end_ts))
            
            for row in cursor.fetchall():
                ts = datetime.fromisoformat(row[0])
                if is_chg_pct:
                    ltp = row[1] or 0.0
                    cp = row[2] or 0.0
                    val = ((ltp - cp) / cp) * 100.0 if cp and cp > 0 else 0.0
                else:
                    val = row[1] or 0.0 # Default to 0 if None
                data_points.append((ts, float(val)))
                
        except Exception as e:
            print(f"Error reading history from DB: {e}")
            messagebox.showerror("Database Error", f"Could not read graph data: {e}")
        finally:
            if conn:
                conn.close()

        if not data_points:
            time_str = f"range {start_date} to {end_date}"
            if minutes > 0:
                time_str = f"last {minutes} minutes"
            messagebox.showinfo(
                "No Data",
                f"No valid data points found for:\n"
                f"Instrument: {instrument_key}\n"
                f"Field: {display_key}\n"
                f"Time: {time_str}"
            )

        return data_points, display_key
    
    def plot_graph(self, instrument_key, data_key_path, minutes):
        """Plot graph in separate window."""
        
        display_key = "Chg %" if data_key_path == ["Chg %"] else ".".join(data_key_path)

        original_text = self.refresh_button.cget("text")
        self.refresh_button.config(text="Loading graph...", state="disabled")
        self.root.update()
        
        def load_and_plot(original_text_arg):
            try:
                historical_data, display_key = self.get_historical_data(instrument_key, data_key_path, minutes)
                self.root.after_idle(lambda: self._show_plot(instrument_key, display_key, 
                                                             historical_data, minutes, original_text_arg))
            except Exception as e:
                print(f"Error loading graph data: {e}")
                self.root.after_idle(lambda: self.refresh_button.config(text=original_text_arg, state="normal"))
        
        threading.Thread(target=lambda: load_and_plot(original_text), daemon=True).start()

    def _show_plot(self, instrument_key, display_key, historical_data, minutes, original_btn_text):
        """Show plot on main thread."""
        self.refresh_button.config(text=original_btn_text, state="normal")
        
        if not historical_data:
            return
        
        try: 
            timestamps, values = zip(*historical_data)
        except ValueError:
            messagebox.showinfo("No Data", "No points to plot.")
            return
        
        graph_window = tk.Toplevel(self.root)
        time_str = f"Last {minutes} Mins" if minutes > 0 else f"Date Range"
        graph_window.title(f"Graph: {instrument_key} - {display_key} ({time_str})")
        graph_window.geometry("900x650")
        
        fig = Figure(figsize=(8, 5.5), dpi=100)
        ax = fig.add_subplot(111)
        ax.plot(timestamps, values, label=display_key, linewidth=2, color='#2E86AB')
        
        # --- FIX: New Date/Time Formatting ---
        if (timestamps[-1] - timestamps[0]).days > 0:
            # Format for multi-day: 31 Oct 2025 03:00PM
            date_format = DateFormatter('%d %b %Y %I:%M%p')
        else:
            # Format for single-day: 03:00:15 PM
            date_format = DateFormatter('%I:%M:%S %p')
        
        ax.xaxis.set_major_formatter(date_format)
        # --- END FIX ---
            
        ax.xaxis.set_major_locator(ticker.MaxNLocator(nbins=10, prune='both'))
        fig.autofmt_xdate()
        ax.set_title(f"{instrument_key} - {display_key}", fontsize=12, fontweight='bold')
        ax.set_ylabel(display_key, fontsize=10)
        ax.set_xlabel("Time", fontsize=10)
        ax.grid(True, linestyle='--', alpha=0.6)
        ax.legend(loc='best')
        fig.tight_layout()
        
        canvas = FigureCanvasTkAgg(fig, master=graph_window)
        canvas.draw()
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # --- ADD INTERACTIVE TOOLBAR ---
        toolbarFrame = ttk.Frame(master=graph_window)
        toolbarFrame.pack(side=tk.BOTTOM, fill=tk.X)
        toolbar = NavigationToolbar2Tk(canvas, toolbarFrame)
        toolbar.update()
        # --- END ---

    def prompt_for_custom_time(self, instrument_key, data_key_path):
        """Ask user for custom minutes."""
        minutes = simpledialog.askinteger(
            "Custom Time", 
            "Enter time in minutes:",
            parent=self.root,
            minvalue=1,
            maxvalue=10080 # 7 days
        )
        if minutes:
            self.plot_graph(instrument_key, data_key_path, minutes)

    def show_context_menu(self, event):
        """Show context menu for graphing options on right-click."""
        popup = None
        try:
            item_id = self.tree.identify_row(event.y)
            if not item_id: return

            values = self.tree.item(item_id)['values']
            if not values: return
                
            strike_str = str(values[self.tree['columns'].index('strike')])
            if strike_str not in self.chain_data: return

            popup = tk.Menu(self.root, tearoff=0)
            
            # These are the *display labels* in the right-click menu
            # And the old data_key_paths that get_historical_data will translate
            graph_options = [
                ("LTP", ["fullFeed", "marketFF", "ltpc", "ltp"]),
                ("Chg %", ["Chg %"]),
                ("OI", ["fullFeed", "marketFF", "oi"]),
                ("IV", ["fullFeed", "marketFF", "iv"]),
                ("Delta", ["fullFeed", "marketFF", "optionGreeks", "delta"]),
                ("Gamma", ["fullFeed", "marketFF", "optionGreeks", "gamma"]),
                ("Vega", ["fullFeed", "marketFF", "optionGreeks", "vega"]),
                ("Theta", ["fullFeed", "marketFF", "optionGreeks", "theta"])
            ]
            
            # Add Call options
            if "CE" in self.chain_data[strike_str]:
                ce_key = self.chain_data[strike_str]["CE"]
                call_menu = tk.Menu(popup, tearoff=0)
                popup.add_cascade(label="Call Graphs", menu=call_menu)
                
                for minutes in [5, 15, 30, 60, 0]:
                    time_str = f"Last {minutes} mins" if minutes > 0 else "Full Range"
                    for label, data_key_path in graph_options:
                        call_menu.add_command(
                            label=f"{label} ({time_str})",
                            command=lambda k=ce_key, path=data_key_path, m=minutes: 
                                self.plot_graph(k, path, m)
                        )
                    if minutes != 0: call_menu.add_separator()
                
                call_menu.add_separator()
                custom_submenu = tk.Menu(call_menu, tearoff=0)
                call_menu.add_cascade(label="Custom...", menu=custom_submenu)
                for label, data_key_path in graph_options:
                    custom_submenu.add_command(
                        label=f"{label}",
                        command=lambda k=ce_key, path=data_key_path:
                            self.prompt_for_custom_time(k, path)
                    )

            # Add Put options
            if "PE" in self.chain_data[strike_str]:
                pe_key = self.chain_data[strike_str]["PE"]
                put_menu = tk.Menu(popup, tearoff=0)
                popup.add_cascade(label="Put Graphs", menu=put_menu)
                
                for minutes in [5, 15, 30, 60, 0]:
                    time_str = f"Last {minutes} mins" if minutes > 0 else "Full Range"
                    for label, data_key_path in graph_options:
                        put_menu.add_command(
                            label=f"{label} ({time_str})",
                            command=lambda k=pe_key, path=data_key_path, m=minutes: 
                                self.plot_graph(k, path, m)
                        )
                    if minutes != 0: put_menu.add_separator()

                put_menu.add_separator()
                custom_submenu_put = tk.Menu(put_menu, tearoff=0)
                put_menu.add_cascade(label="Custom...", menu=custom_submenu_put)
                for label, data_key_path in graph_options:
                    custom_submenu_put.add_command(
                        label=f"{label}",
                        command=lambda k=pe_key, path=data_key_path:
                            self.prompt_for_custom_time(k, path)
                    )

            popup.tk_popup(event.x_root, event.y_root)
            
        except Exception as e:
            print(f"Error showing context menu: {e}")
        finally:
            if popup:
                try:
                    popup.grab_release()
                except:
                    pass

# --- Main execution ---
if __name__ == "__main__":
    if not os.path.exists(DB_FILE):
        messagebox.showerror("Database Not Found", 
            f"Error: Database file '{DB_FILE}' not found.\n\n"
            "Please run 'create_db.py' one time to create the database file before running this dashboard."
        )
    else:
        if not os.path.exists(RESOURCES_DIR):
             os.makedirs(RESOURCES_DIR)
        
        root = tk.Tk()
        app = OptionChainDashboard(root)
        root.mainloop()