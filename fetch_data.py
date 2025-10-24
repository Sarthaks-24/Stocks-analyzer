import json
import os
import glob
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.dates import DateFormatter
import matplotlib.ticker as ticker

# --- Constants ---
DATA_DIR = "data"
RESOURCES_DIR = "resources"
REFRESH_RATE_MS = 2000  # Refresh data every 2 seconds
CACHE_STALE_SECONDS = 1  # How old cached data can be (must be < REFRESH_RATE)

# --- Main Application Class ---

class OptionChainDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("Option Chain Dashboard")
        self.root.geometry("1600x800") # Made wider for more columns

        # --- Data Storage ---
        self.chain_file_var = tk.StringVar()
        self.chain_data = {}  # Stores the strike-to-key mapping (e.g., nifty-....json)
        self.instrument_map = {}  # Reverse map: {instrument_key: (strike, type, item_id)}
        self.live_data_cache = {}  # Caches last-read data: {key: (read_time, data)}

        # --- Setup GUI ---
        self.setup_gui()
        self.load_available_chains()

        # --- Start auto-refresh ---
        self.auto_refresh_data()

    def setup_gui(self):
        """Creates the main GUI layout."""
        
        # --- Top Control Frame ---
        top_frame = ttk.Frame(self.root, padding="10")
        top_frame.pack(fill=tk.X)

        ttk.Label(top_frame, text="Select Option Chain:").pack(side=tk.LEFT, padx=(0, 5))
        
        self.chain_dropdown = ttk.Combobox(
            top_frame, 
            textvariable=self.chain_file_var, 
            state="readonly", 
            width=40
        )
        self.chain_dropdown.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.chain_dropdown.bind("<<ComboboxSelected>>", self.on_chain_select)

        self.refresh_button = ttk.Button(
            top_frame, 
            text="Refresh Now", 
            command=self.update_all_rows
        )
        self.refresh_button.pack(side=tk.LEFT, padx=10)

        # --- Main Treeview (Option Chain) ---
        tree_frame = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        tree_frame.pack(fill=tk.BOTH, expand=True)

        # Added more columns as seen in the Sensibull screenshot
        columns = (
            "call_oi_chg", "call_oi", "call_ltp", 
            "strike", 
            "put_ltp", "put_oi", "put_oi_chg"
        )
        
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings")
        
        # --- Define Headings (CALLS) ---
        self.tree.heading("call_oi_chg", text="OI Chg %")
        self.tree.heading("call_oi", text="Call OI")
        self.tree.heading("call_ltp", text="Call LTP")
        
        # --- Define Headings (STRIKE) ---
        self.tree.heading("strike", text="Strike")
        
        # --- Define Headings (PUTS) ---
        self.tree.heading("put_ltp", text="Put LTP")
        self.tree.heading("put_oi", text="Put OI")
        self.tree.heading("put_oi_chg", text="OI Chg %")


        # --- Define Column properties (CALLS) ---
        self.tree.column("call_oi_chg", width=100, anchor=tk.E)
        self.tree.column("call_oi", width=100, anchor=tk.E)
        self.tree.column("call_ltp", width=100, anchor=tk.E)
        
        # --- Define Column properties (STRIKE) ---
        self.tree.column("strike", width=100, anchor=tk.CENTER)
        
        # --- Define Column properties (PUTS) ---
        self.tree.column("put_ltp", width=100, anchor=tk.W)
        self.tree.column("put_oi", width=100, anchor=tk.W)
        self.tree.column("put_oi_chg", width=100, anchor=tk.W)

        # --- Style Configuration (Sensibull Look) ---
        style = ttk.Style()
        style.configure("Treeview", rowheight=28, font=('Helvetica', 10))
        style.configure("Treeview.Heading", font=('Helvetica', 10, 'bold'))
        
        # Alternating row colors
        self.tree.tag_configure("oddrow", background="#FAFAFA")
        self.tree.tag_configure("evenrow", background="#FFFFFF")
        
        # Style for the central strike column
        self.tree.tag_configure("strike_cell", background="#F0F8FF", font=('Helvetica', 10, 'bold'))
        # Style for "in-the-money" calls
        self.tree.tag_configure("itm_call", background="#FFF8DC")
        # Style for "in-the-money" puts
        self.tree.tag_configure("itm_put", background="#FFF8DC")


        # Add Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        vsb.pack(side='right', fill='y')
        hsb.pack(side='bottom', fill='x')
        self.tree.pack(side='left', fill='both', expand=True)

        # --- Bind Right-Click ---
        self.tree.bind("<Button-3>", self.show_context_menu)


    # --- Data Loading and Refreshing ---

    def load_available_chains(self):
        """Finds generated JSON files in the resources directory."""
        try:
            search_pattern = os.path.join(RESOURCES_DIR, "*-*-*.json")
            chain_files = [os.path.basename(f) for f in glob.glob(search_pattern)]
            
            if not chain_files:
                messagebox.showwarning("No Chains Found", 
                    f"No option chain files (*-*-*.json) found in '{RESOURCES_DIR}'."
                    "\nPlease run `search.py` and use 'Build Option Files' first.")
                return
                
            self.chain_dropdown['values'] = chain_files
            if chain_files:
                self.chain_dropdown.set(chain_files[0])
                self.on_chain_select()
                
        except Exception as e:
            messagebox.showerror("Error Loading Chains", f"Failed to scan resources dir: {e}")

    def on_chain_select(self, event=None):
        """Loads the selected option chain file into the Treeview."""
        filename = self.chain_file_var.get()
        if not filename:
            return

        filepath = os.path.join(RESOURCES_DIR, filename)
        
        try:
            with open(filepath, 'r') as f:
                self.chain_data = json.load(f)
            
            self.populate_tree_skeleton()
            self.update_all_rows()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load chain file '{filename}': {e}")
            self.chain_data = {}
            self.instrument_map = {}

    def populate_tree_skeleton(self):
        """Clears and re-populates the tree with just the strike prices."""
        # Clear old data
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.instrument_map.clear()
        self.live_data_cache.clear()

        if not self.chain_data:
            return
            
        # Sort strikes numerically (keys are strings in JSON)
        try:
            sorted_strikes = sorted(self.chain_data.keys(), key=float)
        except ValueError:
            sorted_strikes = sorted(self.chain_data.keys()) # Fallback to string sort

        for i, strike in enumerate(sorted_strikes):
            tags = ("evenrow",) if i % 2 == 0 else ("oddrow",)
            
            # Insert the row with just the strike price
            item_id = self.tree.insert(
                "", "end", 
                values=("", "", "", strike, "", "", ""),
                tags=tags
            )
            
            # Update the instrument map for quick lookup
            if "CE" in self.chain_data[strike]:
                ce_key = self.chain_data[strike]["CE"]
                self.instrument_map[ce_key] = (strike, "CE", item_id)
            if "PE" in self.chain_data[strike]:
                pe_key = self.chain_data[strike]["PE"]
                self.instrument_map[pe_key] = (strike, "PE", item_id)

    def auto_refresh_data(self):
        """Periodically calls the update function."""
        try:
            self.update_all_rows()
        except Exception as e:
            print(f"Error during auto-refresh: {e}")
        finally:
            self.root.after(REFRESH_RATE_MS, self.auto_refresh_data)

    def update_all_rows(self):
        """Iterates all tree rows and updates them with the latest data."""
        if not self.instrument_map:
            return # Nothing to update
            
        for item_id in self.tree.get_children():
            try:
                strike_str = self.tree.item(item_id)['values'][3] 
                if strike_str not in self.chain_data:
                    continue

                ce_key = self.chain_data[strike_str].get("CE")
                pe_key = self.chain_data[strike_str].get("PE")

                ce_data = self.get_latest_data(ce_key) if ce_key else {}
                pe_data = self.get_latest_data(pe_key) if pe_key else {}

                # Update Call data
                self.tree.set(item_id, "call_ltp", f"{ce_data.get('marketLtp', 0.0):.2f}")
                self.tree.set(item_id, "call_oi", ce_data.get("openInterest", "N/A"))
                self.tree.set(item_id, "call_oi_chg", f"{ce_data.get('percentChange', 0):.1f}%")

                # Update Put data
                self.tree.set(item_id, "put_ltp", f"{pe_data.get('marketLtp', 0.0):.2f}")
                self.tree.set(item_id, "put_oi", pe_data.get("openInterest", "N/A"))
                self.tree.set(item_id, "put_oi_chg", f"{pe_data.get('percentChange', 0):.1f}%")
                
            except Exception as e:
                print(f"Error updating row for strike {strike_str}: {e}")
                
    def get_latest_data(self, instrument_key):
        """
        Gets the latest data tick for an instrument.
        Uses a cache to avoid re-reading the same file repeatedly.
        Reads the *last line* of the data file.
        """
        now = datetime.now()
        
        # Check cache first
        if instrument_key in self.live_data_cache:
            read_time, data = self.live_data_cache[instrument_key]
            if (now - read_time).total_seconds() < CACHE_STALE_SECONDS:
                return data

        # --- Cache is stale or missing, read the file ---
        try:
            safe_key = instrument_key.replace("|", "_")
            today = now.strftime('%Y-%m-%d')
            filepath = os.path.join(DATA_DIR, safe_key, f"{today}.json")

            if not os.path.exists(filepath):
                return {} # No file, no data

            # Read the last line of the file (robustly)
            last_line = ""
            with open(filepath, 'rb') as f:
                try:  
                    f.seek(-2, os.SEEK_END)
                    while f.read(1) != b'\n':
                        f.seek(-2, os.SEEK_CUR)
                except IOError: 
                    f.seek(0)
                
                last_line = f.readline().decode('utf-8')

            if not last_line:
                return {}

            # This part MUST match the format in fetch_data.py
            data = json.loads(last_line)
            feed_data = data.get("feed", {}) # We expect the {"feed": ...} wrapper
            
            if not feed_data:
                # This can happen if the JSON is malformed or doesn't have "feed"
                # This will show as N/A, which is correct
                print(f"WARN: 'feed' key not found in last line of {filepath}")
                return {}

            # Update cache
            self.live_data_cache[instrument_key] = (now, feed_data)
            return feed_data

        except json.JSONDecodeError:
            print(f"WARN: Could not decode JSON from last line of {filepath}")
            return {} # File is likely being written, return empty
        except Exception as e:
            # Catch other errors like permissions, file not found during read, etc.
            print(f"Error reading latest data for {instrument_key}: {e}")
            return {} # Return empty dict on failure

    # --- Graphing Functionality ---

    def show_context_menu(self, event):
        """Displays a right-click menu to show graphs."""
        item_id = self.tree.identify_row(event.y)
        col_id = self.tree.identify_column(event.x)
        
        if not item_id:
            return

        # Get the 'id' of the column, e.g., "call_ltp"
        col_name = self.tree.column(col_id, "id")
        
        # Get the strike price from the row's values (column index 3)
        strike = self.tree.item(item_id)['values'][3]
        if strike not in self.chain_data:
            return
        
        instrument_key = None
        data_key = None # The key inside the 'feed' object (e.g., marketLtp)

        if col_name.startswith("call_"):
            instrument_key = self.chain_data[strike].get("CE")
            if col_name == "call_ltp": data_key = "marketLtp"
            elif col_name == "call_oi": data_key = "openInterest"
            elif col_name == "call_oi_chg": data_key = "percentChange"
            
        elif col_name.startswith("put_"):
            instrument_key = self.chain_data[strike].get("PE")
            if col_name == "put_ltp": data_key = "marketLtp"
            elif col_name == "put_oi": data_key = "openInterest"
            elif col_name == "put_oi_chg": data_key = "percentChange"

        # If they didn't click a graphable cell, do nothing
        if not instrument_key or not data_key:
            return

        # Create the menu
        menu = tk.Menu(self.root, tearoff=0)
        submenu = tk.Menu(menu, tearoff=0)
        
        # Add time options
        time_options = [1, 5, 15, 30, 60] # in minutes
        for minutes in time_options:
            submenu.add_command(
                label=f"Last {minutes} Mins", 
                command=lambda m=minutes: self.plot_graph(instrument_key, data_key, m)
            )
        submenu.add_separator()
        submenu.add_command(
            label="All Day", 
            command=lambda: self.plot_graph(instrument_key, data_key, 0) # 0 means all day
        )
        
        menu.add_cascade(label=f"Graph {data_key}", menu=submenu)
        
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def get_historical_data(self, instrument_key, data_key, minutes):
        """
        Reads the *entire* data file for an instrument and filters by time.
        """
        safe_key = instrument_key.replace("|", "_")
        today = datetime.now().strftime('%Y-%m-%d')
        filepath = os.path.join(DATA_DIR, safe_key, f"{today}.json")

        if not os.path.exists(filepath):
            messagebox.showwarning("No Data", f"Data file not found:\n{filepath}")
            return []

        data_points = []
        now = datetime.now()
        time_filter = (now - timedelta(minutes=minutes)) if minutes > 0 else datetime.min

        try:
            # We open with 'r' which is safe even if 'a+' handle is open
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        line_data = json.loads(line)
                        
                        # This part MUST match the format in fetch_data.py
                        ts_str = line_data.get("timestamp")
                        feed = line_data.get("feed")
                        
                        if not ts_str or not feed:
                            continue # Skip malformed line

                        ts = datetime.fromisoformat(ts_str)

                        # Apply time filter
                        if ts >= time_filter:
                            val = feed.get(data_key)
                            if val is not None:
                                # Append the (timestamp, value) tuple
                                data_points.append((ts, float(val)))
                    
                    except (json.JSONDecodeError, TypeError, ValueError):
                        # Skip bad line, e.g., half-written line
                        continue 
        
        except Exception as e:
            messagebox.showerror("Error Reading History", f"Could not read file {filepath}:\n{e}")
            return []
            
        return data_points

    def plot_graph(self, instrument_key, data_key, minutes):
        """Fetches historical data and plots it in a new window."""
        
        historical_data = self.get_historical_data(instrument_key, data_key, minutes)
        
        if not historical_data:
            messagebox.showinfo("No Data", f"No data found for {instrument_key} in the selected time range.")
            return

        try:
            timestamps, values = zip(*historical_data)
        except ValueError:
            messagebox.showinfo("No Data", "No data points to plot.")
            return

        # Create a new top-level window for the graph
        graph_window = tk.Toplevel(self.root)
        time_str = f"Last {minutes} Mins" if minutes > 0 else "All Day"
        graph_window.title(f"Graph: {instrument_key} - {data_key} ({time_str})")
        graph_window.geometry("800x600")

        fig = plt.figure.Figure(figsize=(7, 5), dpi=100)
        ax = fig.add_subplot(111)
        
        ax.plot(timestamps, values, label=data_key)
        
        # Format the x-axis to show time
        ax.xaxis.set_major_formatter(DateFormatter('%H:%M:%S'))
        ax.xaxis.set_major_locator(ticker.MaxNLocator(nbins=10, prune='auto'))
        fig.autofmt_xdate()
        
        ax.set_title(f"{instrument_key} - {data_key}")
        ax.set_ylabel(data_key)
        ax.set_xlabel("Time")
        ax.grid(True, linestyle='--', alpha=0.6)
        
        canvas = FigureCanvasTkAgg(fig, master=graph_window)
        canvas.draw()
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

# --- Main execution ---
if __name__ == "__main__":
    # Ensure directories exist (though fetch_data should also do this)
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(RESOURCES_DIR, exist_ok=True)
    
    root = tk.Tk()
    app = OptionChainDashboard(root)
    root.mainloop()