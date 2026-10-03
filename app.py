"""SecureSteg desktop app (Tkinter).   Run:  python app.py"""
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image

import stego
from database import Database

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "securesteg.db")
IMAGE_TYPES = [("Images", "*.png *.bmp *.jpg *.jpeg"), ("All files", "*.*")]


def safe(action):
    """Wrap a button action so errors show up as a message box instead of crashing the app."""
    def wrapper():
        try:
            action()
        except ValueError as e:       # expected problems: wrong password, no image selected...
            messagebox.showwarning("SecureSteg", str(e))
        except Exception as e:        # anything else
            messagebox.showerror("SecureSteg", f"Unexpected error: {e}")
    return wrapper


def open_image():
    """Ask the user for an image. Returns (image, path), or (None, None) if cancelled."""
    path = filedialog.askopenfilename(title="Select image", filetypes=IMAGE_TYPES)
    if not path:
        return None, None
    with Image.open(path) as img:
        return img.convert("RGB"), path


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SecureSteg")
        self.geometry("760x560")
        ttk.Style(self).theme_use("clam")
        self.db = Database(DB_PATH)
        self.screen = None
        self.show_login()

    def new_screen(self):
        """Destroy the current screen (and everything typed in it) and return a fresh one."""
        if self.screen:
            self.screen.destroy()
        self.screen = ttk.Frame(self, padding=16)
        self.screen.pack(fill="both", expand=True)
        return self.screen

    # ---------------- Login screen ----------------
    def show_login(self):
        self.user_id = None
        box = ttk.Frame(self.new_screen())
        box.place(relx=0.5, rely=0.4, anchor="center")
        ttk.Label(box, text="🔒 SecureSteg", font=("Helvetica", 18, "bold")).pack(pady=10)
        ttk.Label(box, text="Username").pack(anchor="w")
        username = ttk.Entry(box, width=30)
        username.pack()
        ttk.Label(box, text="Password").pack(anchor="w", pady=(8, 0))
        password = ttk.Entry(box, width=30, show="•")
        password.pack()

        def submit(register):
            if register:
                self.db.register(username.get(), password.get())
            self.user_id = self.db.login(username.get(), password.get())
            self.show_main(username.get().strip())

        ttk.Button(box, text="Login", command=safe(lambda: submit(False))).pack(fill="x", pady=(12, 4))
        ttk.Button(box, text="Register", command=safe(lambda: submit(True))).pack(fill="x")

    # ---------------- Main screen ----------------
    def show_main(self, username):
        screen = self.new_screen()
        top = ttk.Frame(screen)
        top.pack(fill="x", pady=(0, 8))
        ttk.Label(top, text=f"Signed in as {username}").pack(side="left")
        ttk.Button(top, text="Logout", command=self.show_login).pack(side="right")

        tabs = ttk.Notebook(screen)
        tabs.pack(fill="both", expand=True)
        encode_tab, decode_tab, history_tab = (ttk.Frame(tabs, padding=12) for _ in range(3))
        tabs.add(encode_tab, text="Encode")
        tabs.add(decode_tab, text="Decode")
        tabs.add(history_tab, text="History")
        self.build_encode_tab(encode_tab)
        self.build_decode_tab(decode_tab)
        self.build_history_tab(history_tab)
        tabs.bind("<<NotebookTabChanged>>", lambda e: self.refresh_history())

    # ---------------- Encode tab ----------------
    def build_encode_tab(self, tab):
        self.cover = None         # the image we hide data in
        self.cover_path = ""
        self.attached = ""        # path of a file to hide (instead of typed text)

        row = ttk.Frame(tab)
        row.pack(fill="x")
        ttk.Button(row, text="Select image…", command=safe(self.choose_cover)).pack(side="left")
        self.cover_label = ttk.Label(row, text="No image selected")
        self.cover_label.pack(side="left", padx=8)

        ttk.Label(tab, text="Secret message:").pack(anchor="w", pady=(10, 0))
        self.message = tk.Text(tab, height=8, wrap="word")
        self.message.pack(fill="both", expand=True)

        row = ttk.Frame(tab)
        row.pack(fill="x", pady=6)
        ttk.Button(row, text="…or attach a file", command=self.attach_file).pack(side="left")
        self.attach_label = ttk.Label(row)
        self.attach_label.pack(side="left", padx=8)

        row = ttk.Frame(tab)
        row.pack(fill="x")
        ttk.Label(row, text="Password (optional - turns on AES encryption):").pack(side="left")
        self.encode_password = ttk.Entry(row, width=24, show="•")
        self.encode_password.pack(side="left", padx=8)

        ttk.Button(tab, text="Encode & Save", command=safe(self.encode)).pack(pady=12)

    def choose_cover(self):
        image, path = open_image()
        if image:
            self.cover, self.cover_path = image, path
            kb = stego.capacity(image) / 1024
            self.cover_label.config(text=f"{os.path.basename(path)}  (can hide about {kb:,.1f} KB)")

    def attach_file(self):
        self.attached = filedialog.askopenfilename(title="Select a file to hide")
        self.attach_label.config(text=os.path.basename(self.attached))

    def encode(self):
        if self.cover is None:
            raise ValueError("Select an image first.")
        if self.attached:
            with open(self.attached, "rb") as f:
                data = f.read()
            filename = os.path.basename(self.attached)
        else:
            data, filename = self.message.get("1.0", "end").strip().encode(), ""
            if not data:
                raise ValueError("Type a message or attach a file.")
        password = self.encode_password.get()

        result = stego.hide(self.cover, data, filename, password)
        path = filedialog.asksaveasfilename(title="Save encoded image", defaultextension=".png",
                                            filetypes=[("PNG image", "*.png")])
        if not path:
            return
        path = os.path.splitext(path)[0] + ".png"   # always PNG: JPEG compression destroys hidden bits
        result.save(path)
        self.db.add_history(self.user_id, path, "encode", bool(password))

        mse, psnr = stego.quality(self.cover, result)
        used = 100 * len(data) / stego.capacity(self.cover)
        messagebox.showinfo("Saved", f"Saved to {path}\n\n"
                                     f"Hidden data: {len(data):,} bytes ({used:.2f}% of capacity)\n"
                                     f"Encrypted: {'Yes' if password else 'No'}\n"
                                     f"MSE: {mse:.5f}\nPSNR: {psnr:.2f} dB")

    # ---------------- Decode tab ----------------
    def build_decode_tab(self, tab):
        self.stego_image = None
        self.stego_path = ""

        row = ttk.Frame(tab)
        row.pack(fill="x")
        ttk.Button(row, text="Select image…", command=safe(self.choose_stego)).pack(side="left")
        self.stego_label = ttk.Label(row, text="No image selected")
        self.stego_label.pack(side="left", padx=8)

        row = ttk.Frame(tab)
        row.pack(fill="x", pady=10)
        ttk.Label(row, text="Password (if encrypted):").pack(side="left")
        self.decode_password = ttk.Entry(row, width=24, show="•")
        self.decode_password.pack(side="left", padx=8)
        ttk.Button(row, text="Decode", command=safe(self.decode)).pack(side="left")

        ttk.Label(tab, text="Hidden message:").pack(anchor="w")
        self.output = tk.Text(tab, height=10, wrap="word")
        self.output.pack(fill="both", expand=True)

    def choose_stego(self):
        image, path = open_image()
        if image:
            self.stego_image, self.stego_path = image, path
            self.stego_label.config(text=os.path.basename(path))

    def decode(self):
        if self.stego_image is None:
            raise ValueError("Select an image first.")
        password = self.decode_password.get()
        data, filename = stego.reveal(self.stego_image, password)
        self.db.add_history(self.user_id, self.stego_path, "decode", bool(password))

        self.output.delete("1.0", "end")
        if not filename:                          # it was a text message
            self.output.insert("end", data.decode())
            return
        path = filedialog.asksaveasfilename(title="Save hidden file", initialfile=filename)
        if path:
            with open(path, "wb") as f:
                f.write(data)
            self.output.insert("end", f"Hidden file '{filename}' saved to {path}")

    # ---------------- History tab ----------------
    def build_history_tab(self, tab):
        row = ttk.Frame(tab)
        row.pack(fill="x", pady=(0, 8))
        ttk.Label(row, text="Search:").pack(side="left")
        self.search = ttk.Entry(row, width=30)
        self.search.pack(side="left", padx=8)
        self.search.bind("<KeyRelease>", lambda e: self.refresh_history())   # filter while typing

        columns = ("Date", "Action", "Encrypted", "File")
        self.tree = ttk.Treeview(tab, columns=columns, show="headings")
        for col, width in zip(columns, (140, 70, 80, 400)):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=width)
        self.tree.pack(fill="both", expand=True)

    def refresh_history(self):
        self.tree.delete(*self.tree.get_children())
        for date, action, encrypted, path in self.db.get_history(self.user_id, self.search.get()):
            self.tree.insert("", "end", values=(date, action, "Yes" if encrypted else "No", path))


if __name__ == "__main__":
    App().mainloop()
