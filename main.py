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
        # Device selection with port info
        self.port_var = tk.StringVar()
        self.port_info = {}  # Store port information
        self.port_combo = ttk.Combobox(control_frame, textvariable=self.port_var, width=50)
        self.port_combo.grid(row=0, column=0, padx=5, sticky='ew')
        self.port_combo.bind('<<ComboboxSelected>>', self.on_port_selected)
        
        # Info label for additional port details
        self.port_info_label = ttk.Label(control_frame, text="", wraplength=400)
        self.port_info_label.grid(row=1, column=0, columnspan=5, padx=5, pady=(2, 0), sticky='w')
        
        # Set minimum window size
        self.root.update()
        self.root.minsize(self.root.winfo_width(), self.root.winfo_height())

        # Add auto-reconnect checkbox
        self.auto_reconnect = tk.BooleanVar()
        self.auto_reconnect_check = ttk.Checkbutton(control_frame, text="Auto-reconnect", 
                                                   variable=self.auto_reconnect)
        self.auto_reconnect_check.grid(row=0, column=5, padx=5)
        
        # Add variables for tracking reconnection
        self.target_vid = None
        self.target_pid = None
        self.reconnect_thread = None
        self.attempting_reconnect = False

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
            self.port_info = {}
            
            for port in serial.tools.list_ports.comports():
                # Create a detailed port description
                description = f"{port.device}"
                if port.description:
                    description += f" - {port.description}"
                
                # Store additional information
                self.port_info[description] = {
                    'device': port.device,
                    'name': port.name,
                    'description': port.description,
                    'hwid': port.hwid,
                    'vid': port.vid,
                    'pid': port.pid,
                    'serial_number': port.serial_number,
                    'manufacturer': port.manufacturer,
                    'product': port.product,
                }
                
                # Windows: COM ports
                if sys.platform.startswith('win'):
                    if 'COM' in port.device:
                        ports.append(description)
                # Linux/Unix: tty devices
                else:
                    if ('tty' in port.device.lower() and
                        ('acm' in port.device.lower() or 'usb' in port.device.lower())):
                        ports.append(description)
            
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
            self.update_port_info(ports[0])
    
    def on_port_selected(self, event):
        """Handle port selection change."""
        selected = self.port_var.get()
        self.update_port_info(selected)
    
    def update_port_info(self, selected):
        """Update the port information label."""
        if selected in self.port_info:
            info = self.port_info[selected]
            details = []
            
            if info['manufacturer']:
                details.append(f"Manufacturer: {info['manufacturer']}")
            if info['product']:
                details.append(f"Product: {info['product']}")
            if info['serial_number']:
                details.append(f"Serial: {info['serial_number']}")
            if info['vid'] is not None and info['pid'] is not None:
                details.append(f"VID:PID = {info['vid']:04X}:{info['pid']:04X}")
            
            info_text = " | ".join(details) if details else "No additional information available"
            self.port_info_label.configure(text=info_text)
        else:
            self.port_info_label.configure(text="")
    
    def toggle_connection(self):
        """Handle connection/disconnection to serial port."""
        if not self.is_connected:
            try:
                selected = self.port_var.get()
                if selected in self.port_info:
                    port = self.port_info[selected]['device']
                    baud = int(self.baud_var.get())
                    self.serial_port = serial.Serial(port, baud, timeout=0.1)
                    self.is_connected = True
                    self.connect_button.configure(text="Disconnect")
                    self.add_message(f"Connected to {selected} at {baud} baud", "system")
                    
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
                    # Read raw data first
                    data = self.serial_port.readline()
                    
                    # Try to decode as UTF-8, if it fails, show as hex
                    try:
                        message = data.decode().strip()
                        display_text = message
                    except UnicodeDecodeError:
                        # Format as hex if we can't decode as UTF-8
                        hex_values = ' '.join([f'{b:02X}' for b in data])
                        display_text = f'[HEX] {hex_values}'
                    
                    if display_text:
                        if not (self.filter_wait.get() and display_text.lower() == "wait"):
                            self.root.after(0, lambda d=display_text: self.add_message(d, "received"))
                            
            except Exception as e:
                self.root.after(0, lambda: self.add_message(f"Read error: {str(e)}", "error"))
                self.root.after(0, self.disconnect)
                break

    def send_message(self):
        """Send message to serial port."""
        message = self.message_var.get().strip()
        if message and self.is_connected:
            try:
                # Check if the message is a hex string
                if message.startswith('0x') or message.startswith('0X'):
                    # Convert hex string to bytes
                    try:
                        # Remove 0x prefix and spaces
                        hex_str = message[2:].replace(' ', '')
                        data = bytes.fromhex(hex_str)
                        self.serial_port.write(data)
                        self.add_message(f"[HEX] {' '.join([f'{b:02X}' for b in data])}", "sent")
                    except ValueError as e:
                        self.add_message(f"Invalid hex format: {str(e)}", "error")
                        return
                else:
                    # Normal text message
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
        

    def toggle_connection(self):
        """Handle connection/disconnection to serial port."""
        if not self.is_connected:
            try:
                selected = self.port_var.get()
                if selected in self.port_info:
                    port_info = self.port_info[selected]
                    port = port_info['device']
                    baud = int(self.baud_var.get())
                    
                    # Store VID/PID for auto-reconnect
                    self.target_vid = port_info['vid']
                    self.target_pid = port_info['pid']
                    
                    self.serial_port = serial.Serial(port, baud, timeout=0.1)
                    self.is_connected = True
                    self.connect_button.configure(text="Disconnect")
                    self.add_message(f"Connected to {selected} at {baud} baud", "system")
                    
                    # Start reading thread
                    self.read_thread = threading.Thread(target=self.read_serial, daemon=True)
                    self.read_thread.start()
            except Exception as e:
                self.add_message(f"Connection error: {str(e)}", "error")
                if self.auto_reconnect.get():
                    self.start_reconnection()
        else:
            self.disconnect()

    def disconnect(self):
        """Disconnect from serial port."""
        if self.serial_port:
            self.serial_port.close()
        self.is_connected = False
        self.connect_button.configure(text="Connect")
        self.add_message("Disconnected", "system")
        
        # Start reconnection if auto-reconnect is enabled
        if self.auto_reconnect.get() and self.target_vid is not None:
            self.start_reconnection()

    def start_reconnection(self):
        """Start the reconnection thread if not already running."""
        if not self.attempting_reconnect:
            self.attempting_reconnect = True
            self.reconnect_thread = threading.Thread(target=self.reconnection_loop, daemon=True)
            self.reconnect_thread.start()

    def reconnection_loop(self):
        """Attempt to reconnect to the device with matching VID/PID."""
        while self.auto_reconnect.get() and not self.is_connected:
            try:
                # Search for device with matching VID/PID
                for port in serial.tools.list_ports.comports():
                    if (port.vid == self.target_vid and 
                        port.pid == self.target_pid):
                        # Update port selection in GUI
                        description = f"{port.device}"
                        if port.description:
                            description += f" - {port.description}"
                        
                        # Set port in GUI and attempt connection
                        self.root.after(0, lambda: self.port_var.set(description))
                        self.root.after(100, self.attempt_reconnect)  # Small delay to let GUI update
                        break
                
                time.sleep(2)  # Wait before next attempt
            except Exception as e:
                self.root.after(0, lambda: self.add_message(f"Reconnection error: {str(e)}", "error"))
                time.sleep(2)
        
        self.attempting_reconnect = False

    def attempt_reconnect(self):
        """Attempt to reconnect to the currently selected port."""
        if not self.is_connected:
            self.toggle_connection()

    def read_serial(self):
        """Read data from serial port."""
        while self.is_connected and self.serial_port:
            try:
                if self.serial_port.in_waiting:
                    data = self.serial_port.readline()
                    try:
                        message = data.decode().strip()
                        display_text = message
                    except UnicodeDecodeError:
                        hex_values = ' '.join([f'{b:02X}' for b in data])
                        display_text = f'[HEX] {hex_values}'
                    
                    if display_text:
                        if not (self.filter_wait.get() and display_text.lower() == "wait"):
                            self.root.after(0, lambda d=display_text: self.add_message(d, "received"))
            except Exception as e:
                self.root.after(0, lambda: self.add_message(f"Read error: {str(e)}", "error"))
                self.root.after(0, self.disconnect)
                break

    def on_closing(self):
        """Clean up when closing the application."""
        self.running = False
        self.auto_reconnect.set(False)  # Disable auto-reconnect before closing
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