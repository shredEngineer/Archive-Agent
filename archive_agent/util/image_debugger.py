#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import threading
from typing import List, Tuple
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import ttk


IndexedImage = Tuple[Image.Image, int, int]


def show_images(images: List[IndexedImage]) -> None:
    """
    Launch image viewer window in a new thread.

    :param images: List of tuples (PIL.Image, page number, image index per page).
    """
    thread = threading.Thread(target=_run_viewer, args=(images,), daemon=True)
    thread.start()


def _run_viewer(images: List[IndexedImage]) -> None:
    """
    Display images in a scrollable, framed layout with metadata using tkinter.
    """
    if not images:
        return

    root = tk.Tk()
    root.title("Archive Agent: PDF Image Debugger")
    root.geometry("800x600")

    frame = ttk.Frame(root)
    frame.pack(fill="both", expand=True)

    canvas = tk.Canvas(frame, borderwidth=0)
    scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
    scroll_frame = ttk.Frame(canvas)

    scroll_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    max_height = 300
    image_refs = []

    for img, page_num, img_index in images:
        aspect_ratio = img.width / img.height
        height = min(img.height, max_height)
        width = int(height * aspect_ratio)

        # noinspection PyUnresolvedReferences
        resized = img.resize((width, height), Image.LANCZOS)
        tk_img = ImageTk.PhotoImage(resized)
        image_refs.append(tk_img)  # Prevent GC

        container = ttk.Frame(scroll_frame, padding=8, borderwidth=1, relief="solid")
        container.pack(padx=12, pady=8, fill="x", expand=True)

        label_image = ttk.Label(container, image=tk_img)
        label_image.pack()

        meta_lines = [
            f"Image ({img_index}) on page ({page_num})",
            f"{img.width} x {img.height} px",
        ]
        if img.format:
            meta_lines.append(f"Format: {img.format}")
        if img.mode:
            meta_lines.append(f"Mode: {img.mode}")

        label_meta = ttk.Label(container, text="\n".join(meta_lines), anchor="center", justify="center")
        label_meta.pack(pady=(6, 0))

    root.mainloop()
