import json
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

class StockFilterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Instrument Key Finder & Selector")
        self.root.geometry("1400x700")

        self.data, self.data_map = self.load_and_process_data()
        self.selected_keys = set()
        self.selected_instrument_data = {} # Stores full data for selected instruments

        # --- Filter variables ---
        self.search_var = tk.StringVar()
        self.search_mode_var = tk.StringVar(value="Starts With")
        self.strike_price_var = tk.StringVar()
        self.expiry_date_var = tk.StringVar()
        self.exact_expiry_date_var = tk.StringVar()
        self.exchange_var = tk.StringVar()
        self.segment_var = tk.StringVar()
        self.instrument_type_var = tk.StringVar()

        # --- Main Layout: A PanedWindow for resizable sections ---
        main_paned_window = ttk.PanedWindow(root, orient=tk.HORIZONTAL)
        main_paned_window.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        left_frame = ttk.Frame(main_paned_window, padding="10")
        main_paned_window.add(left_frame, weight=3)
        right_frame = ttk.Frame(main_paned_window, padding="10")
        main_paned_window.add(right_frame, weight=1)

        # ==========================================================
        # CONFIGURE WIDGETS FOR THE LEFT (MAIN) FRAME
        # ==========================================================
        top_frame = ttk.Frame(left_frame); top_frame.pack(fill=tk.X, pady=5)
        ttk.Label(top_frame, text="Search:").grid(row=0, column=0, padx=(0, 5), pady=5, sticky="w")
        search_entry = ttk.Entry(top_frame, textvariable=self.search_var, width=40); search_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        search_entry.bind("<KeyRelease>", self.update_results)
        search_mode_menu = ttk.Combobox(top_frame, textvariable=self.search_mode_var, values=["Starts With", "Contains", "Exact Match"], width=12); search_mode_menu.grid(row=0, column=2, padx=5, pady=5)
        search_mode_menu.bind("<<ComboboxSelected>>", self.update_results)
        ttk.Label(top_frame, text="Strike Price:").grid(row=0, column=3, padx=(10, 5), pady=5, sticky="w")
        self.strike_price_menu = ttk.OptionMenu(top_frame, self.strike_price_var, "All Strikes"); self.strike_price_menu.grid(row=0, column=4, padx=5, pady=5, sticky="w")
        top_frame.columnconfigure(1, weight=1)

        date_frame = ttk.Frame(left_frame); date_frame.pack(fill=tk.X, pady=5)
        ttk.Label(date_frame, text="Expiry (YYYY-MM):").pack(side=tk.LEFT, padx=(0, 5))
        expiry_date_entry = ttk.Entry(date_frame, textvariable=self.expiry_date_var); expiry_date_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        expiry_date_entry.bind("<KeyRelease>", self.update_results)
        ttk.Label(date_frame, text="or Exact (YYYY-MM-DD):").pack(side=tk.LEFT, padx=(10, 5))
        exact_expiry_date_entry = ttk.Entry(date_frame, textvariable=self.exact_expiry_date_var); exact_expiry_date_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        exact_expiry_date_entry.bind("<KeyRelease>", self.update_results)

        filter_frame = ttk.Frame(left_frame); filter_frame.pack(fill=tk.X, pady=5)
        ttk.Label(filter_frame, text="Exchange:").pack(side=tk.LEFT, padx=(0, 5))
        self.exchange_menu = ttk.OptionMenu(filter_frame, self.exchange_var, "All Exchanges", *self.get_unique_values('exchange'), command=self.update_segment_options); self.exchange_menu.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Label(filter_frame, text="Segment:").pack(side=tk.LEFT, padx=5)
        self.segment_menu = ttk.OptionMenu(filter_frame, self.segment_var, "All Segments", command=self.update_instrument_type_options); self.segment_menu.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Label(filter_frame, text="Type:").pack(side=tk.LEFT, padx=5)
        self.instrument_type_menu = ttk.OptionMenu(filter_frame, self.instrument_type_var, "All Types", command=self.update_results); self.instrument_type_menu.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        results_frame = ttk.LabelFrame(left_frame, text="Results (Double-click or use button to add)"); results_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        columns = ("instrument_key", "name", "trading_symbol", "strike_price", "expiry")
        self.tree = ttk.Treeview(results_frame, columns=columns, show="headings")
        self.tree.heading("instrument_key", text="Instrument Key"); self.tree.heading("name", text="Name"); self.tree.heading("trading_symbol", text="Trading Symbol"); self.tree.heading("strike_price", text="Strike"); self.tree.heading("expiry", text="Expiry Date")
        self.tree.column("instrument_key", width=150); self.tree.column("name", width=250); self.tree.column("trading_symbol", width=120); self.tree.column("strike_price", width=80); self.tree.column("expiry", width=100)
        vsb = ttk.Scrollbar(results_frame, orient="vertical", command=self.tree.yview); hsb = ttk.Scrollbar(results_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side='right', fill='y'); hsb.pack(side='bottom', fill='x'); self.tree.pack(side='left', fill='both', expand=True)
        self.tree.bind("<Double-1>", self.add_to_selection)

        bottom_frame_left = ttk.Frame(left_frame); bottom_frame_left.pack(fill=tk.X, pady=(5,0))
        self.copy_key_button = ttk.Button(bottom_frame_left, text="Copy Key", command=self.copy_instrument_key); self.copy_key_button.pack(side=tk.LEFT, padx=5)
        self.add_button = ttk.Button(bottom_frame_left, text="Add to Selection ->", command=self.add_to_selection); self.add_button.pack(side=tk.LEFT, padx=5)
        self.add_all_button = ttk.Button(bottom_frame_left, text="Add All Filtered", command=self.add_all_to_selection); self.add_all_button.pack(side=tk.LEFT, padx=5)
        self.clear_filters_button = ttk.Button(bottom_frame_left, text="Clear Filters", command=self.clear_filters); self.clear_filters_button.pack(side=tk.RIGHT, padx=5)

        # ==========================================================
        # CONFIGURE WIDGETS FOR THE RIGHT (SIDEBAR) FRAME
        # ==========================================================
        sidebar_frame = ttk.LabelFrame(right_frame, text="Selected Instruments"); sidebar_frame.pack(fill=tk.BOTH, expand=True)
        selected_columns = ("instrument_key", "name")
        self.selected_tree = ttk.Treeview(sidebar_frame, columns=selected_columns, show="headings")
        self.selected_tree.heading("instrument_key", text="Instrument Key"); self.selected_tree.heading("name", text="Name")
        self.selected_tree.column("instrument_key", width=150); self.selected_tree.column("name", width=200)
        sel_vsb = ttk.Scrollbar(sidebar_frame, orient="vertical", command=self.selected_tree.yview); sel_hsb = ttk.Scrollbar(sidebar_frame, orient="horizontal", command=self.selected_tree.xview)
        self.selected_tree.configure(yscrollcommand=sel_vsb.set, xscrollcommand=sel_hsb.set)
        sel_vsb.pack(side='right', fill='y'); sel_hsb.pack(side='bottom', fill='x'); self.selected_tree.pack(fill='both', expand=True)
        bottom_frame_right = ttk.Frame(right_frame); bottom_frame_right.pack(fill=tk.X, pady=(10,0))
        self.remove_button = ttk.Button(bottom_frame_right, text="Remove Selected", command=self.remove_from_selection); self.remove_button.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        self.submit_button = ttk.Button(bottom_frame_right, text="Submit to File", command=self.submit_selections, style="Accent.TButton"); self.submit_button.pack(side=tk.RIGHT, padx=5, expand=True, fill=tk.X)
        ttk.Style().configure("Accent.TButton", foreground="blue", font=('Helvetica', 10, 'bold'))
        self.update_results()

    # --- UPDATED AND NEW METHODS ---

    def add_instrument(self, instrument_key, name):
        """Helper function to add a single instrument to the selection."""
        if instrument_key not in self.selected_keys:
            full_item = self.data_map.get(instrument_key)
            if full_item:
                self.selected_keys.add(instrument_key)
                self.selected_instrument_data[instrument_key] = full_item
                self.selected_tree.insert("", "end", values=(instrument_key, name))
                return True
        return False

    def add_to_selection(self, event=None):
        selected_item = self.tree.focus()
        if not selected_item:
            messagebox.showinfo("Add Instrument", "Please select an instrument from the results list.")
            return
        item_details = self.tree.item(selected_item)
        instrument_key, name, *_ = item_details.get("values")
        if not self.add_instrument(instrument_key, name):
            messagebox.showinfo("Add Instrument", "This instrument has already been added.")

    def add_all_to_selection(self):
        all_item_ids = self.tree.get_children()
        if not all_item_ids:
            messagebox.showinfo("Add All", "There are no results to add.")
            return
        added_count = sum(1 for item_id in all_item_ids if self.add_instrument(*self.tree.item(item_id).get("values")[:2]))
        if added_count > 0:
            messagebox.showinfo("Add All", f"Added {added_count} new instrument(s) to the selection.")
        else:
            messagebox.showinfo("Add All", "All currently displayed instruments were already in the selection list.")

    def remove_from_selection(self):
        selected_item = self.selected_tree.focus()
        if not selected_item:
            messagebox.showinfo("Remove Instrument", "Please select an instrument to remove.")
            return
        item_details = self.selected_tree.item(selected_item)
        instrument_key, *_ = item_details.get("values")
        if instrument_key in self.selected_keys: self.selected_keys.remove(instrument_key)
        self.selected_instrument_data.pop(instrument_key, None)
        self.selected_tree.delete(selected_item)
        
    def submit_selections(self):
        if not self.selected_keys:
            messagebox.showwarning("Submit", "No instruments selected.")
            return

        choice = messagebox.askyesnocancel("Confirm Save Action", "Do you want to OVERWRITE the files?\n\n- Click 'Yes' to Overwrite.\n- Click 'No' to Append.")
        if choice is None: return

        mode, action_desc = ('w', 'Overwritten') if choice else ('a', 'Appended to')
        keys_to_write = [str(self.selected_tree.item(child)['values'][0]) for child in self.selected_tree.get_children()]
        
        try:
            # Handle the simple .txt file
            with open("resources/instruments.txt", mode) as f:
                if mode == 'a' and f.tell() > 0: f.write('\n')
                f.write('\n'.join(keys_to_write))

            # Handle the detailed .json file
            self.write_json_details(choice)
            
            messagebox.showinfo("Success", f"{len(keys_to_write)} instrument(s) successfully saved.\nFiles were {action_desc}.")
        except IOError as e:
            messagebox.showerror("Error", f"Could not write to file.\nError: {e}")

    def write_json_details(self, overwrite):
        """Handles writing the detailed JSON file, including logic for appending."""
        filename = "resources/instruments_details.json"
        new_data = list(self.selected_instrument_data.values())

        if overwrite:
            final_data = new_data
        else: # Append logic
            try:
                with open(filename, 'r') as f:
                    existing_data = json.load(f)
                if not isinstance(existing_data, list): existing_data = []
            except (FileNotFoundError, json.JSONDecodeError):
                existing_data = []
            
            existing_keys = {item.get('instrument_key') for item in existing_data}
            for item in new_data:
                if item.get('instrument_key') not in existing_keys:
                    existing_data.append(item)
            final_data = existing_data

        with open(filename, 'w') as f:
            json.dump(final_data, f, indent=4, default=str) # default=str handles datetime objects

    def clear_filters(self):
        self.search_var.set(""); self.strike_price_var.set("All Strikes"); self.expiry_date_var.set(""); self.exchange_var.set("All Exchanges")
        self.exact_expiry_date_var.set("")
        self.selected_tree.delete(*self.selected_tree.get_children())
        self.selected_keys.clear()
        self.selected_instrument_data.clear()
        self.update_segment_options()

    def load_and_process_data(self, filename="complete.json"):
        try:
            with open(filename, 'r') as f: data = json.load(f)
            data_map = {}
            for item in data:
                if 'instrument_key' in item: data_map[item['instrument_key']] = item
                if 'expiry' in item and item['expiry']:
                    try: item['expiry_date'] = datetime.fromtimestamp(item['expiry'] / 1000).date()
                    except (ValueError, TypeError): item['expiry_date'] = None
            return data, data_map
        except FileNotFoundError:
            messagebox.showerror("Error", f"File '{filename}' not found. Application will close."); self.root.destroy()
            return [], {}

    # --- UNCHANGED CORE LOGIC ---
    def get_unique_values(self, key, data=None):
        if data is None: data = self.data
        values = set(item.get(key) for item in data if item.get(key) is not None)
        return sorted(list(values))
    def update_dynamic_options(self, menu, var, options, default_text, callback=None):
        current_value = var.get()
        menu['menu'].delete(0, 'end')
        str_options = [str(o) for o in options]
        menu['menu'].add_command(label=default_text, command=tk._setit(var, default_text, callback))
        for option in str_options: menu['menu'].add_command(label=option, command=tk._setit(var, option, callback))
        var.set(current_value if current_value in str_options else default_text)
    def update_segment_options(self, *args):
        exchange = self.exchange_var.get()
        data_source = [d for d in self.data if d.get('exchange') == exchange] if exchange and exchange != "All Exchanges" else self.data
        segment_options = self.get_unique_values('segment', data_source)
        self.update_dynamic_options(self.segment_menu, self.segment_var, segment_options, "All Segments", self.update_instrument_type_options)
        self.update_instrument_type_options()
    def update_instrument_type_options(self, *args):
        exchange, segment = self.exchange_var.get(), self.segment_var.get()
        temp_data = self.data
        if exchange and exchange != "All Exchanges": temp_data = [d for d in temp_data if d.get('exchange') == exchange]
        if segment and segment != "All Segments": temp_data = [d for d in temp_data if d.get('segment') == segment]
        instrument_type_options = self.get_unique_values('instrument_type', temp_data)
        self.update_dynamic_options(self.instrument_type_menu, self.instrument_type_var, instrument_type_options, "All Types", self.update_results)
        self.update_results()
    def update_results(self, *args):
        filtered = self.data
        if self.exchange_var.get() != "All Exchanges": filtered = [d for d in filtered if d.get('exchange') == self.exchange_var.get()]
        if self.segment_var.get() != "All Segments": filtered = [d for d in filtered if d.get('segment') == self.segment_var.get()]
        if self.instrument_type_var.get() != "All Types": filtered = [d for d in filtered if d.get('instrument_type') == self.instrument_type_var.get()]
        search_query = self.search_var.get().lower()
        if search_query:
            mode = self.search_mode_var.get()
            if mode == "Starts With": filtered = [d for d in filtered if str(d.get('name', '')).lower().startswith(search_query) or str(d.get('trading_symbol', '')).lower().startswith(search_query)]
            elif mode == "Exact Match": filtered = [d for d in filtered if str(d.get('name', '')).lower() == search_query or str(d.get('trading_symbol', '')).lower() == search_query]
            else: filtered = [d for d in filtered if search_query in str(d.get('name', '')).lower() or search_query in str(d.get('trading_symbol', '')).lower()]
        current_strike_prices = self.get_unique_values('strike_price', filtered)
        self.update_dynamic_options(self.strike_price_menu, self.strike_price_var, current_strike_prices, "All Strikes", self.update_results)
        strike_price_str = self.strike_price_var.get()
        if strike_price_str not in ["", "All Strikes"]:
            try: filtered = [d for d in filtered if d.get('strike_price') == float(strike_price_str)]
            except ValueError: pass
        exact_expiry_str, expiry_month_str = self.exact_expiry_date_var.get(), self.expiry_date_var.get()
        if exact_expiry_str and len(exact_expiry_str) == 10:
            try: filtered = [d for d in filtered if d.get('expiry_date') and d['expiry_date'] == datetime.strptime(exact_expiry_str, "%Y-%m-%d").date()]
            except ValueError: pass
        elif expiry_month_str and len(expiry_month_str) >= 7:
            try:
                year, month = map(int, expiry_month_str.split('-')[:2])
                filtered = [d for d in filtered if d.get('expiry_date') and d['expiry_date'].year == year and d['expiry_date'].month == month]
            except (ValueError, IndexError): pass
        self.tree.delete(*self.tree.get_children())
        for item in filtered[:1000]:
            expiry_display = item.get('expiry_date', 'N/A')
            if hasattr(expiry_display, 'strftime'): expiry_display = expiry_display.strftime("%Y-%m-%d")
            self.tree.insert("", "end", values=(item.get('instrument_key', 'N/A'), item.get('name', 'N/A'), item.get('trading_symbol', 'N/A'), item.get('strike_price', 'N/A'), expiry_display))
    def copy_instrument_key(self):
        selected_item = self.tree.focus()
        if not selected_item: messagebox.showinfo("Copy Key", "Please select an instrument from the results list."); return
        instrument_key = self.tree.item(selected_item).get("values")[0]
        self.root.clipboard_clear(); self.root.clipboard_append(instrument_key)
        messagebox.showinfo("Copy Key", f"Instrument key copied to clipboard:\n{instrument_key}")

if __name__ == "__main__":
    root = tk.Tk()
    app = StockFilterApp(root)
    root.mainloop()