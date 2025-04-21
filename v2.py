import tkinter as tk
from tkinter import ttk
from tkinter import filedialog, messagebox
import os
import subprocess
import tempfile
import shutil
import requests
from bs4 import BeautifulSoup

class OpenHaxTool(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Open Hax Tool")
        self.temp_dir = None
        self.exefs_dir = None
        self.romfs_dir = None
        self.code_bin_path = None
        self.setup_menu()
        self.setup_gui()

    def setup_menu(self):
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open .cia", command=self.open_cia)
        file_menu.add_command(label="Save .cia", command=self.save_cia)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit)
        menubar.add_cascade(label="File", menu=file_menu)
        self.config(menu=menubar)

    def setup_gui(self):
        self.tree = ttk.Treeview(self)
        self.tree.pack(side=tk.LEFT, fill=tk.Y)
        self.tree.bind("<Double-1>", self.on_tree_double_click)
        self.tree.bind("<Button-3>", self.on_right_click)
        
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        self.hex_tab = tk.Frame(self.notebook)
        self.asm_tab = tk.Frame(self.notebook)
        self.replace_tab = tk.Frame(self.notebook)
        self.ars_tab = tk.Frame(self.notebook)  # New ARS Scripts tab
        
        self.notebook.add(self.hex_tab, text="Hex Editor")
        self.notebook.add(self.asm_tab, text="ASM Injector")
        self.notebook.add(self.replace_tab, text="File Replace")
        self.notebook.add(self.ars_tab, text="ARS Scripts")
        
        # Hex Editor
        self.hex_text = tk.Text(self.hex_tab, height=20, width=50)
        self.hex_text.pack(fill=tk.BOTH, expand=True)
        tk.Button(self.hex_tab, text="Save Changes", command=self.save_hex).pack()
        
        # ASM Injector
        self.asm_text = tk.Text(self.asm_tab, height=20, width=50)
        self.asm_text.pack(fill=tk.BOTH, expand=True)
        self.offset_entry = tk.Entry(self.asm_tab)
        self.offset_entry.pack()
        tk.Button(self.asm_tab, text="Inject ASM", command=self.inject_asm).pack()
        
        # File Replace
        tk.Button(self.replace_tab, text="Replace Selected File", command=self.replace_file).pack()
        
        # ARS Scripts Tab
        self.ars_search_entry = tk.Entry(self.ars_tab)
        self.ars_search_entry.pack(pady=5)
        tk.Button(self.ars_tab, text="Search ARS Scripts", command=self.search_ars_scripts).pack(pady=5)
        self.ars_listbox = tk.Listbox(self.ars_tab, height=20, width=50)
        self.ars_listbox.pack(fill=tk.BOTH, expand=True, pady=5)
        tk.Button(self.ars_tab, text="Import Selected Script", command=self.import_ars_script).pack(pady=5)

    def open_cia(self):
        cia_path = filedialog.askopenfilename(filetypes=[("CIA files", "*.cia")])
        if not cia_path:
            return
        self.temp_dir = tempfile.mkdtemp()
        subprocess.run(["ctrtool", "-p", "--content=contents", cia_path], cwd=self.temp_dir)
        content_path = os.path.join(self.temp_dir, "contents.0000.00000000")
        self.exefs_dir = os.path.join(self.temp_dir, "exefs")
        self.romfs_dir = os.path.join(self.temp_dir, "romfs")
        os.makedirs(self.exefs_dir, exist_ok=True)
        os.makedirs(self.romfs_dir, exist_ok=True)
        subprocess.run(["3dstool", "-x", "-t", "ncch", "--exefs-dir", self.exefs_dir, "--romfs-dir", self.romfs_dir, content_path])
        self.code_bin_path = os.path.join(self.exefs_dir, "code.bin")
        self.populate_tree()

    def populate_tree(self):
        self.tree.delete(*self.tree.get_children())
        exefs_id = self.tree.insert("", "end", text="exefs")
        romfs_id = self.tree.insert("", "end", text="romfs")
        
        for root, dirs, files in os.walk(self.exefs_dir):
            rel_path = os.path.relpath(root, self.exefs_dir)
            parent = exefs_id if rel_path == "." else self.tree.insert(exefs_id, "end", text=rel_path)
            for file in files:
                full_path = os.path.join(root, file)
                self.tree.insert(parent, "end", text=file, values=(full_path,))
        
        for root, dirs, files in os.walk(self.romfs_dir):
            rel_path = os.path.relpath(root, self.romfs_dir)
            parent = romfs_id if rel_path == "." else self.tree.insert(romfs_id, "end", text=rel_path)
            for file in files:
                full_path = os.path.join(root, file)
                self.tree.insert(parent, "end", text=file, values=(full_path,))

    def on_tree_double_click(self, event):
        selected = self.tree.selection()
        if not selected:
            return
        full_path = self.tree.item(selected[0])['values'][0]
        with open(full_path, "rb") as f:
            data = f.read()
        hex_str = ' '.join(f'{b:02x}' for b in data)
        self.hex_text.delete("1.0", tk.END)
        self.hex_text.insert("1.0", hex_str)

    def save_hex(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showerror("Error", "No file selected")
            return
        full_path = self.tree.item(selected[0])['values'][0]
        hex_str = self.hex_text.get("1.0", tk.END).strip()
        try:
            data = bytes.fromhex(hex_str)
            with open(full_path, "wb") as f:
                f.write(data)
            messagebox.showinfo("Success", "File saved")
        except ValueError:
            messagebox.showerror("Error", "Invalid hex string")

    def inject_asm(self):
        if not self.code_bin_path:
            messagebox.showerror("Error", "No .cia loaded")
            return
        asm_code = self.asm_text.get("1.0", tk.END).strip()
        offset_str = self.offset_entry.get().strip()
        try:
            offset = int(offset_str, 16)
            with open("temp.s", "w") as f:
                f.write(asm_code)
            subprocess.run(["armips", "temp.s", "-o", "temp.bin"])
            if not os.path.exists("temp.bin"):
                raise Exception("Assembly failed")
            with open("temp.bin", "rb") as f:
                patch_data = f.read()
            with open(self.code_bin_path, "r+b") as f:
                f.seek(offset)
                f.write(patch_data)
            messagebox.showinfo("Success", "ASM injected")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def replace_file(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showerror("Error", "No file selected")
            return
        full_path = self.tree.item(selected[0])['values'][0]
        new_file = filedialog.askopenfilename()
        if new_file:
            shutil.copy(new_file, full_path)
            messagebox.showinfo("Success", "File replaced")

    def save_cia(self):
        if not self.temp_dir:
            messagebox.showerror("Error", "No .cia loaded")
            return
        output_path = filedialog.asksaveasfilename(defaultextension=".cia", filetypes=[("CIA files", "*.cia")])
        if not output_path:
            return
        content_path = os.path.join(self.temp_dir, "contents.0000.00000000")
        subprocess.run(["3dstool", "-c", "-t", "ncch", "--exefs-dir", self.exefs_dir, "--romfs-dir", self.romfs_dir, content_path])
        content_files = [f for f in os.listdir(self.temp_dir) if f.startswith("contents.")]
        content_args = []
        for content_file in sorted(content_files):
            index = content_file.split('.')[1]
            content_args.extend(["-content", f"{content_file}:{index}:{index}"])
        subprocess.run(["makerom", "-f", "cia", "-o", output_path] + content_args, cwd=self.temp_dir)
        messagebox.showinfo("Success", "CIA saved")

    def on_right_click(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            menu = tk.Menu(self, tearoff=0)
            menu.add_command(label="Export", command=self.export_item)
            menu.post(event.x_root, event.y_root)

    def export_item(self):
        selected = self.tree.selection()
        if not selected:
            return
        item = selected[0]
        parent = item
        while parent:
            parent_text = self.tree.item(parent)['text']
            if parent_text in ["exefs", "romfs"]:
                root = parent_text
                break
            parent = self.tree.parent(parent)
        else:
            messagebox.showerror("Error", "Invalid selection")
            return

        base_dir = self.exefs_dir if root == "exefs" else self.romfs_dir
        item_text = self.tree.item(item)['text']

        if self.tree.item(item)['values']:
            full_path = self.tree.item(item)['values'][0]
            is_dir = False
        else:
            if item_text == root:
                full_path = base_dir
            else:
                full_path = os.path.join(base_dir, item_text)
            is_dir = True

        dest_dir = filedialog.askdirectory(title="Select Destination Directory")
        if not dest_dir:
            return
        dest_path = os.path.join(dest_dir, item_text)

        try:
            if is_dir:
                shutil.copytree(full_path, dest_path)
                messagebox.showinfo("Success", f"Directory '{item_text}' exported successfully")
            else:
                shutil.copy(full_path, dest_path)
                messagebox.showinfo("Success", f"File '{item_text}' exported successfully")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export: {str(e)}")

    def search_ars_scripts(self):
        """Search for ARS scripts on a forum based on user input."""
        search_term = self.ars_search_entry.get().strip()
        if not search_term:
            messagebox.showerror("Error", "Please enter a search term")
            return

        # Replace with an actual ARS forum URL or archive (e.g., Wayback Machine link)
        forum_url = f"https://example-forum.com/search?q={search_term}"
        try:
            response = requests.get(forum_url)
            response.raise_for_status()  # Check for HTTP errors
            soup = BeautifulSoup(response.content, 'html.parser')
            # Adjust selector based on actual forum HTML structure
            scripts = soup.select('.script-title')  # Example class name
            self.ars_listbox.delete(0, tk.END)
            if not scripts:
                self.ars_listbox.insert(tk.END, "No scripts found")
            for script in scripts:
                script_name = script.get_text(strip=True)
                self.ars_listbox.insert(tk.END, script_name)
        except requests.RequestException as e:
            messagebox.showerror("Error", f"Failed to connect to forum: {str(e)}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to parse scripts: {str(e)}")

    def import_ars_script(self):
        """Import the selected ARS script into the ASM Injector."""
        selected_script = self.ars_listbox.get(tk.ACTIVE)
        if not selected_script or selected_script == "No scripts found":
            messagebox.showerror("Error", "No valid script selected")
            return

        # Construct URL for the script (example, adjust as needed)
        script_url = f"https://example-forum.com/scripts/{selected_script.replace(' ', '-')}"
        try:
            response = requests.get(script_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            # Adjust selector based on actual forum HTML structure
            script_code = soup.find('pre', class_='script-code')  # Example tag and class
            if not script_code:
                raise ValueError("Script code not found on page")
            script_content = script_code.get_text(strip=True)
            self.asm_text.delete("1.0", tk.END)
            self.asm_text.insert("1.0", script_content)
            messagebox.showinfo("Success", f"Script '{selected_script}' imported into ASM Injector")
        except requests.RequestException as e:
            messagebox.showerror("Error", f"Failed to fetch script: {str(e)}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to import script: {str(e)}")

if __name__ == "__main__":
    app = OpenHaxTool()
    app.mainloop()
