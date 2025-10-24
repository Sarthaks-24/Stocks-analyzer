import json
import os
import glob
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.dates import DateFormatter
import matplotlib.ticker as ticker

# --- Constants ---
DATA_DIR = "data"
RESOURCES_DIR = "resources"
REFRESH_RATE_MS = 2000  # Refresh data every 2 seconds
CACHE_STALE_SECONDS = 1  # How old cached data can be

# --- Main Application Class ---
class OptionChainDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("Option Chain Dashboard")
        self.root.geometry("2000x800") 

        self.chain_file_var = tk.StringVar()
        self.chain_data = {}
        self.instrument_map = {}
        self.live_data_cache = {}

        self.setup_gui()
        self.load_available_chains()
        self.auto_refresh_data()

    def setup_gui(self):
        """Creates the main GUI layout."""
        top_frame = ttk.Frame(self.root, padding="10")
        top_frame.pack(fill=tk.X)
        ttk.Label(top_frame, text="Select Option Chain:").pack(side=tk.LEFT, padx=(0, 5))
        self.chain_dropdown = ttk.Combobox(
            top_frame, textvariable=self.chain_file_var, state="readonly", width=40
        )
        self.chain_dropdown.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.chain_dropdown.bind("<<ComboboxSelected>>", self.on_chain_select)
        self.refresh_button = ttk.Button(
            top_frame, text="Refresh Now", command=self.update_all_rows
        )
        self.refresh_button.pack(side=tk.LEFT, padx=10)

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
        self.tree.column("call_oi_chg_pct", width=col_width, anchor=tk.E)
        self.tree.column("call_oi", width=col_width, anchor=tk.E)
        self.tree.column("call_ltp", width=col_width, anchor=tk.E)
        self.tree.column("call_iv", width=greek_width, anchor=tk.E) 
        self.tree.column("call_delta", width=greek_width, anchor=tk.E) 
        self.tree.column("call_gamma", width=greek_width, anchor=tk.E) 
        self.tree.column("call_vega", width=greek_width, anchor=tk.E) 
        self.tree.column("call_theta", width=greek_width, anchor=tk.E) 
        self.tree.column("strike", width=80, anchor=tk.CENTER)
        self.tree.column("put_theta", width=greek_width, anchor=tk.W) 
        self.tree.column("put_vega", width=greek_width, anchor=tk.W) 
        self.tree.column("put_gamma", width=greek_width, anchor=tk.W) 
        self.tree.column("put_delta", width=greek_width, anchor=tk.W) 
        self.tree.column("put_iv", width=greek_width, anchor=tk.W) 
        self.tree.column("put_ltp", width=col_width, anchor=tk.W)
        self.tree.column("put_oi", width=col_width, anchor=tk.W)
        self.tree.column("put_oi_chg_pct", width=col_width, anchor=tk.W)

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

    def load_available_chains(self):
        try:
            search_pattern = os.path.join(RESOURCES_DIR, "*-*-*.json")
            chain_files = [os.path.basename(f) for f in glob.glob(search_pattern)]
            if not chain_files:
                messagebox.showwarning("No Chains", f"No option chain files found in '{RESOURCES_DIR}'.")
                return
            self.chain_dropdown['values'] = chain_files
            if chain_files:
                self.chain_dropdown.set(chain_files[0])
                self.on_chain_select()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to scan resources dir: {e}")

    def on_chain_select(self, event=None):
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
            messagebox.showerror("Error", f"Failed to load chain '{filename}': {e}")
            self.chain_data, self.instrument_map = {}, {}

    def populate_tree_skeleton(self):
        for item in self.tree.get_children(): 
            self.tree.delete(item)
        self.instrument_map.clear()
        self.live_data_cache.clear()
        if not self.chain_data: 
            return

        try: 
            sorted_strikes = sorted(self.chain_data.keys(), key=float)
        except ValueError: 
            sorted_strikes = sorted(self.chain_data.keys())

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
        try: 
            self.update_all_rows()
        except Exception as e: 
            print(f"Refresh Error: {e}")
        finally: 
            self.root.after(REFRESH_RATE_MS, self.auto_refresh_data)

    def calculate_change_pct(self, ltp, cp):
        """Safely calculates percentage change."""
        if cp is None or cp == 0:
            return 0.0
        try:
            return ((ltp - cp) / cp) * 100.0
        except (ValueError, TypeError, ZeroDivisionError):
            return 0.0

    def safe_get_nested(self, data, *keys, default=None):
        """Safely navigate nested dictionary structure."""
        result = data
        for key in keys:
            if isinstance(result, dict):
                result = result.get(key)
                if result is None:
                    return default
            else:
                return default
        return result if result is not None else default

    def update_all_rows(self):
        """Iterates all tree rows and updates them with the latest data."""
        if not self.instrument_map: 
            return
            
        strike_col_index = self.tree['columns'].index('strike')

        for item_id in self.tree.get_children():
            try:
                strike_str = self.tree.item(item_id)['values'][strike_col_index]
                if strike_str not in self.chain_data: 
                    continue

                ce_key = self.chain_data[strike_str].get("CE")
                pe_key = self.chain_data[strike_str].get("PE")

                ce_latest = self.get_latest_data(ce_key)
                pe_latest = self.get_latest_data(pe_key)
                
                # Navigate to marketFF using safe getter
                ce_market_ff = self.safe_get_nested(ce_latest, 'feed', 'fullFeed', 'marketFF', default={})
                pe_market_ff = self.safe_get_nested(pe_latest, 'feed', 'fullFeed', 'marketFF', default={})

                # --- Extract Call data ---
                call_ltpc = ce_market_ff.get('ltpc', {}) 
                call_greeks = ce_market_ff.get('optionGreeks', {}) 
                
                call_ltp = call_ltpc.get('ltp', 0.0)
                call_cp = call_ltpc.get('cp', 0.0)
                call_oi = ce_market_ff.get('oi', 0.0)
                call_iv = ce_market_ff.get('iv', 0.0)
                call_delta = call_greeks.get('delta', 0.0)
                call_gamma = call_greeks.get('gamma', 0.0)
                call_vega = call_greeks.get('vega', 0.0)
                call_theta = call_greeks.get('theta', 0.0)
                call_chg_pct = self.calculate_change_pct(call_ltp, call_cp)

                # --- Update Call Tree Values ---
                self.tree.set(item_id, "call_ltp", f"{call_ltp:.2f}")
                self.tree.set(item_id, "call_oi", f"{call_oi:.0f}" if isinstance(call_oi, (int, float)) else "N/A")
                self.tree.set(item_id, "call_oi_chg_pct", f"{call_chg_pct:.1f}%")
                self.tree.set(item_id, "call_iv", f"{call_iv:.4f}")
                self.tree.set(item_id, "call_delta", f"{call_delta:.4f}")
                self.tree.set(item_id, "call_gamma", f"{call_gamma:.4f}")
                self.tree.set(item_id, "call_vega", f"{call_vega:.4f}")
                self.tree.set(item_id, "call_theta", f"{call_theta:.4f}")

                # --- Extract Put data ---
                put_ltpc = pe_market_ff.get('ltpc', {}) 
                put_greeks = pe_market_ff.get('optionGreeks', {}) 
                
                put_ltp = put_ltpc.get('ltp', 0.0)
                put_cp = put_ltpc.get('cp', 0.0)
                put_oi = pe_market_ff.get('oi', 0.0)
                put_iv = pe_market_ff.get('iv', 0.0)
                put_delta = put_greeks.get('delta', 0.0)
                put_gamma = put_greeks.get('gamma', 0.0)
                put_vega = put_greeks.get('vega', 0.0)
                put_theta = put_greeks.get('theta', 0.0)
                put_chg_pct = self.calculate_change_pct(put_ltp, put_cp)

                # --- Update Put Tree Values ---
                self.tree.set(item_id, "put_ltp", f"{put_ltp:.2f}")
                self.tree.set(item_id, "put_oi", f"{put_oi:.0f}" if isinstance(put_oi, (int, float)) else "N/A")
                self.tree.set(item_id, "put_oi_chg_pct", f"{put_chg_pct:.1f}%")
                self.tree.set(item_id, "put_iv", f"{put_iv:.4f}")
                self.tree.set(item_id, "put_delta", f"{put_delta:.4f}")
                self.tree.set(item_id, "put_gamma", f"{put_gamma:.4f}")
                self.tree.set(item_id, "put_vega", f"{put_vega:.4f}")
                self.tree.set(item_id, "put_theta", f"{put_theta:.4f}")
                
            except Exception as e:
                print(f"ERROR updating row {strike_str}: {e}")

    def get_latest_data(self, instrument_key):
        if not instrument_key: 
            return {}
        now = datetime.now()
        
        # Check cache
        if instrument_key in self.live_data_cache:
            read_time, data = self.live_data_cache[instrument_key]
            if (now - read_time).total_seconds() < CACHE_STALE_SECONDS: 
                return data
        
        try:
            safe_key = instrument_key.replace("|", "_")
            today = now.strftime('%Y-%m-%d')
            filepath = os.path.join(DATA_DIR, safe_key, f"{today}.json")
            
            if not os.path.exists(filepath): 
                return {}
            
            # Read last line
            last_line = ""
            with open(filepath, 'rb') as f:
                try:  
                    f.seek(-2, os.SEEK_END)
                    while f.read(1) != b'\n':
                        f.seek(-2, os.SEEK_CUR)
                        if f.tell() == 0: 
                            break
                except IOError: 
                    f.seek(0)
                last_line = f.readline().decode('utf-8')
            
            if not last_line: 
                return {}
            
            data = json.loads(last_line)
            
            if "timestamp" not in data or "feed" not in data:
                print(f"WARN: Bad JSON structure in {filepath}")
                return {}
            
            # Cache the complete data structure
            self.live_data_cache[instrument_key] = (now, data)
            return data
            
        except json.JSONDecodeError as e:
            print(f"JSON decode error for {instrument_key}: {e}")
            return self.live_data_cache.get(instrument_key, (None, {}))[1]
        except Exception as e:
            print(f"ERROR reading {instrument_key}: {e}")
            return {}

    # --- Graphing Functionality ---

    def show_context_menu(self, event):
        item_id = self.tree.identify_row(event.y)
        col_id = self.tree.identify_column(event.x)
        if not item_id: 
            return

        col_name = self.tree.column(col_id, "id")
        strike_col_index = self.tree['columns'].index('strike')
        strike = self.tree.item(item_id)['values'][strike_col_index]
        if strike not in self.chain_data: 
            return
        
        instrument_key = None
        data_key_path = None

        if col_name.startswith("call_"):
            instrument_key = self.chain_data[strike].get("CE")
            if col_name == "call_ltp": 
                data_key_path = ("ltpc", "ltp")
            elif col_name == "call_oi": 
                data_key_path = ("oi",)
            elif col_name == "call_iv": 
                data_key_path = ("iv",)
            elif col_name == "call_delta": 
                data_key_path = ("optionGreeks", "delta")
            elif col_name == "call_gamma": 
                data_key_path = ("optionGreeks", "gamma")
            elif col_name == "call_vega": 
                data_key_path = ("optionGreeks", "vega")
            elif col_name == "call_theta": 
                data_key_path = ("optionGreeks", "theta")
            
        elif col_name.startswith("put_"):
            instrument_key = self.chain_data[strike].get("PE")
            if col_name == "put_ltp": 
                data_key_path = ("ltpc", "ltp")
            elif col_name == "put_oi": 
                data_key_path = ("oi",)
            elif col_name == "put_iv": 
                data_key_path = ("iv",)
            elif col_name == "put_delta": 
                data_key_path = ("optionGreeks", "delta")
            elif col_name == "put_gamma": 
                data_key_path = ("optionGreeks", "gamma")
            elif col_name == "put_vega": 
                data_key_path = ("optionGreeks", "vega")
            elif col_name == "put_theta": 
                data_key_path = ("optionGreeks", "theta")

        if not instrument_key or not data_key_path:
            return

        menu = tk.Menu(self.root, tearoff=0)
        submenu = tk.Menu(menu, tearoff=0)
        time_options = [1, 5, 15, 30, 60]
        
        for minutes in time_options:
            submenu.add_command(
                label=f"Last {minutes} Mins", 
                command=lambda m=minutes, p=data_key_path: self.plot_graph(instrument_key, p, m)
            )
        submenu.add_separator()
        submenu.add_command(
            label="All Day", 
            command=lambda p=data_key_path: self.plot_graph(instrument_key, p, 0)
        )
        
        display_key = ".".join(data_key_path)
        menu.add_cascade(label=f"Graph {display_key}", menu=submenu)
        
        try: 
            menu.tk_popup(event.x_root, event.y_root)
        finally: 
            menu.grab_release()

    def get_historical_data(self, instrument_key, data_key_path, minutes):
        safe_key = instrument_key.replace("|", "_")
        today = datetime.now().strftime('%Y-%m-%d')
        filepath = os.path.join(DATA_DIR, safe_key, f"{today}.json")
        
        # Debug: Check if file exists
        if not os.path.exists(filepath):
            # Try to find the directory to see what files are there
            dir_path = os.path.join(DATA_DIR, safe_key)
            if os.path.exists(dir_path):
                available_files = os.listdir(dir_path)
                messagebox.showwarning(
                    "No Data", 
                    f"File not found:\n{filepath}\n\n"
                    f"Available files in directory:\n{', '.join(available_files) if available_files else 'None'}"
                )
            else:
                messagebox.showwarning(
                    "No Data", 
                    f"Directory not found:\n{dir_path}\n\n"
                    f"Make sure data is being collected for instrument:\n{instrument_key}"
                )
            return []
        
        data_points = []
        now = datetime.now()
        time_filter = (now - timedelta(minutes=minutes)) if minutes > 0 else datetime.min
        
        total_lines = 0
        valid_lines = 0
        lines_in_range = 0
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    total_lines += 1
                    try:
                        line_data = json.loads(line)
                        ts_str = line_data.get("timestamp")
                        market_ff = self.safe_get_nested(
                            line_data, 'feed', 'fullFeed', 'marketFF', default=None
                        )
                        
                        if not ts_str or not market_ff: 
                            continue
                        
                        valid_lines += 1
                        ts = datetime.fromisoformat(ts_str)
                        
                        if ts >= time_filter:
                            lines_in_range += 1
                            # Navigate to the specific value
                            val = self.safe_get_nested(market_ff, *data_key_path, default=None)
                            
                            if val is not None:
                                try: 
                                    data_points.append((ts, float(val)))
                                except (ValueError, TypeError): 
                                    pass
                                    
                    except (json.JSONDecodeError, TypeError, ValueError) as e: 
                        continue
            
            # If no data points found, show detailed debug info
            if not data_points:
                display_key = ".".join(data_key_path)
                time_str = f"last {minutes} minutes" if minutes > 0 else "all day"
                messagebox.showinfo(
                    "No Data", 
                    f"No valid data points found for:\n"
                    f"Instrument: {instrument_key}\n"
                    f"Field: {display_key}\n"
                    f"Time range: {time_str}\n\n"
                    f"Debug info:\n"
                    f"- Total lines in file: {total_lines}\n"
                    f"- Valid JSON lines: {valid_lines}\n"
                    f"- Lines in time range: {lines_in_range}\n"
                    f"- Data points extracted: {len(data_points)}"
                )
                
        except Exception as e:
            messagebox.showerror("Read Error", f"Could not read {filepath}:\n{e}")
            return []
            
        return data_points

    def plot_graph(self, instrument_key, data_key_path, minutes):
        display_key = ".".join(data_key_path)
        historical_data = self.get_historical_data(instrument_key, data_key_path, minutes)
        
        if not historical_data:
            # Error message is already shown in get_historical_data
            return
        
        try: 
            timestamps, values = zip(*historical_data)
        except ValueError:
            messagebox.showinfo("No Data", "No points to plot.")
            return
        
        graph_window = tk.Toplevel(self.root)
        time_str = f"Last {minutes} Mins" if minutes > 0 else "All Day"
        graph_window.title(f"Graph: {instrument_key} - {display_key} ({time_str})")
        graph_window.geometry("800x600")
        
        fig = Figure(figsize=(7, 5), dpi=100)
        ax = fig.add_subplot(111)
        ax.plot(timestamps, values, label=display_key, linewidth=2)
        ax.xaxis.set_major_formatter(DateFormatter('%H:%M:%S'))
        ax.xaxis.set_major_locator(ticker.MaxNLocator(nbins=10, prune='both'))
        fig.autofmt_xdate()
        ax.set_title(f"{instrument_key} - {display_key}")
        ax.set_ylabel(display_key)
        ax.set_xlabel("Time")
        ax.grid(True, linestyle='--', alpha=0.6)
        ax.legend()
        fig.tight_layout()
        
        canvas = FigureCanvasTkAgg(fig, master=graph_window)
        canvas.draw()
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

# --- Main execution ---
if __name__ == "__main__":
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(RESOURCES_DIR, exist_ok=True)
    root = tk.Tk()
    app = OptionChainDashboard(root)
    root.mainloop()