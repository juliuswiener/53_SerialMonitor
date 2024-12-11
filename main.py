import tkinter as tk
from tkinter import ttk
import serial
import serial.tools.list_ports
import threading
import time
import re
from collections import deque
import sys

class SerialChatGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Serial Chat")
        
        # Configure root window to scale
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        # Variables
        self.serial_port = None
        self.is_connected = False
        self.command_history = deque(maxlen=100)
        self.history_position = -1
        self.running = True
        self.search_matches = []
        self.current_match = -1
        
        # Main container
        main_frame = ttk.Frame(root)
        main_frame.grid(row=0, column=0, sticky='nsew', padx=10, pady=10)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)  # Make chat area expandable
        
        # Top frame for controls
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=0, column=0, sticky='ew', padx=5, pady=5)
        control_frame.columnconfigure(0, weight=1)  # Make port combo expandable
        
        # Device selection
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(control_frame, textvariable=self.port_var)
        self.port_combo.grid(row=0, column=0, padx=5, sticky='ew')
        
        # Baud rate
        baud_frame = ttk.Frame(control_frame)
        baud_frame.grid(row=0, column=1, padx=5)
        ttk.Label(baud_frame, text="Baud Rate:").grid(row=0, column=0)
        self.baud_var = tk.StringVar(value="115200")
        baud_entry = ttk.Entry(baud_frame, textvariable=self.baud_var, width=10)
        baud_entry.grid(row=0, column=1, padx=5)
        
        # Connect button
        self.connect_button = ttk.Button(control_frame, text="Connect", command=self.toggle_connection)
        self.connect_button.grid(row=0, column=2, padx=5)
        
        # Clear button
        self.clear_button = ttk.Button(control_frame, text="Clear", command=self.clear_chat)
        self.clear_button.grid(row=0, column=3, padx=5)
        
        # Filter checkbox
        self.filter_wait = tk.BooleanVar()
        self.filter_check = ttk.Checkbutton(control_frame, text="Filter 'wait' messages", 
                                          variable=self.filter_wait)
        self.filter_check.grid(row=0, column=4, padx=5)
        
        # Search frame
        search_frame = ttk.Frame(main_frame)
        search_frame.grid(row=1, column=0, sticky='ew', padx=5, pady=5)
        search_frame.columnconfigure(0, weight=1)  # Make search entry expandable
        
        # Search entry
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        self.search_entry.grid(row=0, column=0, sticky='ew', padx=(0, 5))
        
        # Search button
        self.search_button = ttk.Button(search_frame, text="Search", command=self.search_next)
        self.search_button.grid(row=0, column=1)
        
        # Search result label
        self.search_label = ttk.Label(search_frame, text="")
        self.search_label.grid(row=1, column=0, columnspan=2, pady=(2, 0))
        
        # Chat display area with frame
        chat_frame = ttk.Frame(main_frame)
        chat_frame.grid(row=2, column=0, sticky='nsew', pady=5)
        chat_frame.columnconfigure(0, weight=1)
        chat_frame.rowconfigure(0, weight=1)
        
        # Chat display
        self.chat_text = tk.Text(chat_frame, wrap=tk.WORD)
        self.chat_text.grid(row=0, column=0, sticky='nsew')
        
        # Scrollbar for chat
        scrollbar = ttk.Scrollbar(chat_frame, orient=tk.VERTICAL, command=self.chat_text.yview)
        scrollbar.grid(row=0, column=1, sticky='ns')
        self.chat_text.configure(yscrollcommand=scrollbar.set)
        
        # Input frame
        input_frame = ttk.Frame(main_frame)
        input_frame.grid(row=3, column=0, sticky='ew', pady=(5, 0))
        input_frame.columnconfigure(0, weight=1)  # Make message entry expandable
        
        # Message entry
        self.message_var = tk.StringVar()
        self.message_entry = ttk.Entry(input_frame, textvariable=self.message_var)
        self.message_entry.grid(row=0, column=0, sticky='ew', padx=(0, 5))
        
        # Send button
        self.send_button = ttk.Button(input_frame, text="Send", command=self.send_message)
        self.send_button.grid(row=0, column=1)
        
        # Bind events
        self.message_entry.bind('<Up>', self.history_up)
        self.message_entry.bind('<Down>', self.history_down)
        self.search_entry.bind('<Return>', lambda e: self.search_next())
        self.message_entry.bind('<Return>', lambda e: self.send_message())
        
        # Start port update thread
        self.update_ports_thread = threading.Thread(target=self.update_ports_loop, daemon=True)
        self.update_ports_thread.start()
        
        # Set minimum window size
        self.root.update()
        self.root.minsize(self.root.winfo_width(), self.root.winfo_height())

    def clear_chat(self):
        """Clear the chat window."""
        self.chat_text.configure(state=tk.NORMAL)
        self.chat_text.delete(1.0, tk.END)
        self.chat_text.configure(state=tk.DISABLED)
        self.search_matches = []
        self.current_match = -1
        self.search_label.configure(text="")
        
    def update_ports_loop(self):
        """Continuously update the available ports list."""
        while self.running:
            ports = []
            for port in serial.tools.list_ports.comports():
                # Windows: COM ports
                if sys.platform.startswith('win'):
                    if 'COM' in port.device:
                        ports.append(port.device)
                # Linux/Unix: tty devices
                else:
                    if ('tty' in port.device.lower() and
                        ('acm' in port.device.lower() or 'usb' in port.device.lower())):
                        ports.append(port.device)
            
            self.root.after(0, lambda: self.update_ports_list(ports))
            time.sleep(2)
    
    def update_ports_list(self, ports):
        """Update the ports dropdown menu."""
        current = self.port_var.get()
        self.port_combo['values'] = ports
        if current in ports:
            self.port_var.set(current)
        elif ports:
            self.port_var.set(ports[0])
    
    def toggle_connection(self):
        """Handle connection/disconnection to serial port."""
        if not self.is_connected:
            try:
                port = self.port_var.get()
                baud = int(self.baud_var.get())
                self.serial_port = serial.Serial(port, baud, timeout=0.1)
                self.is_connected = True
                self.connect_button.configure(text="Disconnect")
                self.add_message(f"Connected to {port} at {baud} baud", "system")
                
                # Start reading thread
                self.read_thread = threading.Thread(target=self.read_serial, daemon=True)
                self.read_thread.start()
            except Exception as e:
                self.add_message(f"Connection error: {str(e)}", "error")
        else:
            self.disconnect()
    
    def disconnect(self):
        """Disconnect from serial port."""
        if self.serial_port:
            self.serial_port.close()
        self.is_connected = False
        self.connect_button.configure(text="Connect")
        self.add_message("Disconnected", "system")
    
    def read_serial(self):
        """Read data from serial port."""
        while self.is_connected and self.serial_port:
            try:
                if self.serial_port.in_waiting:
                    data = self.serial_port.readline().decode().strip()
                    if data:
                        if not (self.filter_wait.get() and data.lower() == "wait"):
                            self.root.after(0, lambda d=data: self.add_message(d, "received"))
            except Exception as e:
                self.root.after(0, lambda: self.add_message(f"Read error: {str(e)}", "error"))
                self.root.after(0, self.disconnect)
                break
    
    def send_message(self):
        """Send message to serial port."""
        message = self.message_var.get().strip()
        if message and self.is_connected:
            try:
                self.serial_port.write(f"{message}\n".encode())
                self.add_message(message, "sent")
                self.command_history.append(message)
                self.history_position = -1
                self.message_var.set("")
            except Exception as e:
                self.add_message(f"Send error: {str(e)}", "error")
    
    def add_message(self, message, message_type):
        """Add message to chat display."""
        self.chat_text.configure(state=tk.NORMAL)
        if message_type == "sent":
            self.chat_text.insert(tk.END, f"→ {message}\n", "sent")
            self.chat_text.tag_configure("sent", foreground="blue")
        elif message_type == "received":
            self.chat_text.insert(tk.END, f"← {message}\n", "received")
            self.chat_text.tag_configure("received", foreground="green")
        elif message_type == "error":
            self.chat_text.insert(tk.END, f"! {message}\n", "error")
            self.chat_text.tag_configure("error", foreground="red")
        else:
            self.chat_text.insert(tk.END, f"* {message}\n", "system")
            self.chat_text.tag_configure("system", foreground="gray")
        
        self.chat_text.configure(state=tk.DISABLED)
        self.chat_text.see(tk.END)
    
    def history_up(self, event):
        """Navigate up through command history."""
        if self.command_history:
            self.history_position = min(self.history_position + 1, len(self.command_history) - 1)
            self.message_var.set(list(self.command_history)[-self.history_position - 1])
    
    def history_down(self, event):
        """Navigate down through command history."""
        if self.history_position > -1:
            self.history_position -= 1
            if self.history_position == -1:
                self.message_var.set("")
            else:
                self.message_var.set(list(self.command_history)[-self.history_position - 1])
    
    def search_next(self):
        """Search for the next occurrence of the search term."""
        search_term = self.search_var.get().lower()
        if not search_term:
            return
        
        # Get all text
        self.chat_text.configure(state=tk.NORMAL)
        text = self.chat_text.get("1.0", tk.END).lower()
        
        # Find all matches
        self.search_matches = [m.start() for m in re.finditer(re.escape(search_term), text)]
        
        if not self.search_matches:
            self.search_label.configure(text="No matches found")
            self.root.after(2000, lambda: self.search_label.configure(text=""))
            return
        
        # Move to next match
        self.current_match = (self.current_match + 1) % len(self.search_matches)
        match_pos = self.search_matches[self.current_match]
        
        # Convert character position to line.char format
        line_start = "1.0"
        match_pos_tk = self.chat_text.search(search_term, line_start, nocase=True, 
                                           forwards=True, exact=True)
        
        # Scroll to match
        self.chat_text.see(match_pos_tk)
        self.chat_text.configure(state=tk.DISABLED)
        
        # Update search label
        self.search_label.configure(
            text=f"Match {self.current_match + 1} of {len(self.search_matches)}")
        
    def on_closing(self):
        """Clean up when closing the application."""
        self.running = False
        if self.is_connected:
            self.disconnect()
        self.root.destroy()

def main():
    root = tk.Tk()
    app = SerialChatGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    
    # Set initial window size
    root.geometry("800x600")
    
    root.mainloop()

if __name__ == "__main__":
    main()