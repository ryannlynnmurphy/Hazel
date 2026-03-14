#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk, scrolledtext
import subprocess
import threading
import os
import sys

class HazelLauncher:
    def __init__(self, root):
        self.root = root
        self.root.title("Hazel — AI Assistant")
        self.root.geometry("1200x700")
        self.root.configure(bg="#1a1a1a")
        
        self.hazel_process = None
        self.is_running = False
        
        # Header
        header = tk.Frame(root, bg="#242424", height=60)
        header.pack(fill=tk.X)
        
        title = tk.Label(header, text="⬢ Hazel", font=("Playfair Display", 24, "bold"), 
                        fg="#c4a050", bg="#242424")
        title.pack(side=tk.LEFT, padx=20, pady=12)
        
        self.status = tk.Label(header, text="● offline", font=("DM Mono", 11), 
                              fg="#ff6b6b", bg="#242424")
        self.status.pack(side=tk.RIGHT, padx=20, pady=12)
        
        # Main content
        content = tk.Frame(root, bg="#1a1a1a")
        content.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
        
        # Chat pane (left)
        chat_frame = tk.Frame(content, bg="#242424", relief=tk.FLAT, bd=1)
        chat_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        
        chat_label = tk.Label(chat_frame, text="Chat", font=("DM Mono", 10), 
                             fg="#999", bg="#242424")
        chat_label.pack(anchor=tk.W, padx=12, pady=8)
        
        self.chat_box = scrolledtext.ScrolledText(chat_frame, bg="#1a1a1a", fg="#e8e8e8",
                                                   font=("Menlo", 11), wrap=tk.WORD,
                                                   insertbackground="#c4a050")
        self.chat_box.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))
        self.chat_box.config(state=tk.DISABLED)
        
        input_frame = tk.Frame(chat_frame, bg="#242424")
        input_frame.pack(fill=tk.X, padx=12, pady=(0, 12))
        
        self.input_field = tk.Entry(input_frame, bg="#2a2a2a", fg="#e8e8e8", 
                                    font=("Menlo", 11), insertbackground="#c4a050")
        self.input_field.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        self.input_field.bind("<Return>", self.send_message)
        
        send_btn = tk.Button(input_frame, text="→", font=("DM Mono", 12), 
                            bg="#c4a050", fg="white", relief=tk.FLAT, padx=12,
                            command=self.send_message)
        send_btn.pack(side=tk.LEFT)
        
        # Logs pane (right)
        logs_frame = tk.Frame(content, bg="#242424", relief=tk.FLAT, bd=1)
        logs_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(6, 0))
        
        logs_label = tk.Label(logs_frame, text="Terminal", font=("DM Mono", 10), 
                             fg="#999", bg="#242424")
        logs_label.pack(anchor=tk.W, padx=12, pady=8)
        
        self.logs_box = scrolledtext.ScrolledText(logs_frame, bg="#0d0d0d", fg="#66bb6a",
                                                   font=("Menlo", 9), wrap=tk.WORD)
        self.logs_box.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))
        self.logs_box.config(state=tk.DISABLED)
        
        # Controls
        ctrl_frame = tk.Frame(content, bg="#1a1a1a")
        ctrl_frame.pack(fill=tk.X, padx=0, pady=12)
        
        self.start_btn = tk.Button(ctrl_frame, text="▶ Start Hazel", font=("DM Mono", 10),
                                   bg="#66bb6a", fg="white", relief=tk.FLAT, padx=20, pady=8,
                                   command=self.start_hazel)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 6))
        
        self.stop_btn = tk.Button(ctrl_frame, text="⏹ Stop", font=("DM Mono", 10),
                                  bg="#ff6b6b", fg="white", relief=tk.FLAT, padx=20, pady=8,
                                  command=self.stop_hazel, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 6))
        
        open_ui = tk.Button(ctrl_frame, text="🌐 Open UI", font=("DM Mono", 10),
                           bg="#5c7cfa", fg="white", relief=tk.FLAT, padx=20, pady=8,
                           command=self.open_ui)
        open_ui.pack(side=tk.LEFT)
    
    def start_hazel(self):
        if self.is_running:
            return
        
        self.is_running = True
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.status.config(text="● starting...", fg="#ffd43b")
        
        def run():
            os.chdir(os.path.expanduser("~/jarvis"))
            self.hazel_process = subprocess.Popen(
                ["python3", "main.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            self.log_append("✓ Hazel started\n")
            self.status.config(text="● online", fg="#66bb6a")
            
            for line in self.hazel_process.stdout:
                self.log_append(line)
        
        threading.Thread(target=run, daemon=True).start()
    
    def stop_hazel(self):
        if self.hazel_process:
            self.hazel_process.terminate()
            self.hazel_process.wait()
            self.log_append("\n✓ Hazel stopped\n")
        
        self.is_running = False
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.status.config(text="● offline", fg="#ff6b6b")
    
    def send_message(self, event=None):
        msg = self.input_field.get().strip()
        if not msg:
            return
        
        self.chat_append(f"You: {msg}\n")
        self.input_field.delete(0, tk.END)
        
        # TODO: connect to WebSocket
        self.chat_append("Hazel: (thinking...)\n")
    
    def chat_append(self, text):
        self.chat_box.config(state=tk.NORMAL)
        self.chat_box.insert(tk.END, text)
        self.chat_box.see(tk.END)
        self.chat_box.config(state=tk.DISABLED)
    
    def log_append(self, text):
        self.logs_box.config(state=tk.NORMAL)
        self.logs_box.insert(tk.END, text)
        self.logs_box.see(tk.END)
        self.logs_box.config(state=tk.DISABLED)
    
    def open_ui(self):
        import webbrowser
        webbrowser.open("http://localhost:8082/hazel-v5.html")

if __name__ == "__main__":
    root = tk.Tk()
    app = HazelLauncher(root)
    root.mainloop()
