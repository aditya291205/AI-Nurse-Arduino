import time
import json
import queue
import threading
import serial
import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import pyttsx3

PORT = "COM5"  # Update to your port (e.g., /dev/ttyUSB0 on Raspberry Pi)
BAUD = 115200
MAX_POINTS = 100

class AINurseOriginalDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("AI Nurse - Original Sensor Suite & Clinical Guardrails")
        self.root.geometry("1150x750")
        self.root.configure(bg="#0f172a")

        self.data_queue = queue.Queue()
        self.latest_data = {"temp": 0.0, "ir": 0, "lead_plus": 0, "lead_minus": 0, "ecg": 0}
        self.ecg_data = [0] * MAX_POINTS
        self.time_data = list(range(MAX_POINTS))

        self.is_running = True
        self.serial_conn = None

        # Smoothing buffers for high-accuracy readings
        self.temp_buffer = []

        self.create_widgets()
        self.start_serial_thread()
        self.update_gui()

    def speak(self, text):
        def run_speech():
            try:
                engine = pyttsx3.init()
                engine.setProperty("rate", 165)
                engine.say(text)
                engine.runAndWait()
            except Exception as e:
                print(f"TTS Error: {e}")
        threading.Thread(target=run_speech, daemon=True).start()

    def smooth_temp(self, new_temp):
        self.temp_buffer.append(new_temp)
        if len(self.temp_buffer) > 5:
            self.temp_buffer.pop(0)
        return sum(self.temp_buffer) / len(self.temp_buffer)

    def evaluate_clinical_safety(self, data):
        """
        Deterministic safety layer checking temperature and sensor errors.
        Returns 'NORMAL' or an 'ALERT' message.
        """
        temp = data.get("temp", 0)
        lead_p = data.get("lead_plus", 0)
        lead_m = data.get("lead_minus", 0)
        ir = data.get("ir", 0)

        alerts = []

        if lead_p == 1 or lead_m == 1:
            alerts.append("ECG LEADS DISCONNECTED")
        if temp > 38.5:
            alerts.append(f"FEVER ALERT ({temp:.1f}°C)")
        elif temp < 35.0 and temp > 0:
            alerts.append(f"HYPOTHERMIA RISK ({temp:.1f}°C)")
        if ir < 50000 and ir != 0:
            alerts.append("LOW FINGER PRESSURE / NO FINGER ON OXIMETER")

        if alerts:
            return f"🚨 ALERT: {' | '.join(alerts)}"
        return "✅ STATUS: NORMAL"

    def create_widgets(self):
        header_frame = tk.Frame(self.root, bg="#1e293b", height=60)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        title_label = tk.Label(header_frame, text="AI NURSE - SENSOR SUITE & SAFETY MONITOR", font=("Arial", 16, "bold"), fg="#38bdf8", bg="#1e293b")
        title_label.pack(side=tk.LEFT, padx=15, pady=15)

        self.status_label = tk.Label(header_frame, text="Status: Connecting...", font=("Arial", 11, "bold"), fg="#facc15", bg="#1e293b")
        self.status_label.pack(side=tk.RIGHT, padx=15, pady=15)

        main_frame = tk.Frame(self.root, bg="#0f172a")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        sidebar = tk.Frame(main_frame, bg="#1e293b", width=300)
        sidebar.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        self.create_card(sidebar, "BODY TEMP (DS18B20)", "-- °C", "temp_val", "#f97316", 20)
        self.create_card(sidebar, "PULSE OXIMETER (IR)", "--", "ir_val", "#a855f7", 140)
        self.create_card(sidebar, "ECG LEAD STATUS", "Checking...", "lead_val", "#ef4444", 260)

        # Alert Box Card
        alert_card = tk.Frame(sidebar, bg="#334155", width=260, height=140)
        alert_card.place(x=20, y=380)
        alert_card.pack_propagate(False)

        tk.Label(alert_card, text="DETERMINISTIC SAFETY GUARD", font=("Arial", 9, "bold"), fg="#94a3b8", bg="#334155").pack(anchor="w", padx=12, pady=(10, 0))
        
        self.alert_lbl = tk.Label(alert_card, text="System initializing...", font=("Arial", 9, "bold"), fg="#22c55e", bg="#334155", wraplength=230, justify="left")
        self.alert_lbl.pack(anchor="w", padx=12, pady=(5, 10))

        graph_frame = tk.Frame(main_frame, bg="#1e293b")
        graph_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        fig_label = tk.Label(graph_frame, text="LIVE SMOOTHED ECG WAVEFORM (AD8232)", font=("Arial", 11, "bold"), fg="#94a3b8", bg="#1e293b")
        fig_label.pack(anchor="w", padx=15, pady=10)

        self.fig, self.ax = plt.subplots(figsize=(6, 4), dpi=100)
        self.fig.patch.set_facecolor("#1e293b")
        self.ax.set_facecolor("#0f172a")

        self.line, = self.ax.plot(self.time_data, self.ecg_data, color="#22c55e", linewidth=1.5)
        self.ax.set_ylim(0, 1024)
        self.ax.tick_params(colors="white")
        self.ax.grid(True, color="#334155", linestyle="--", alpha=0.5)

        for spine in self.ax.spines.values():
            spine.set_color("#475569")

        self.canvas = FigureCanvasTkAgg(self.fig, master=graph_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))

    def create_card(self, parent, title, initial_val, attr_name, color, y_pos):
        card = tk.Frame(parent, bg="#334155", width=260, height=100)
        card.place(x=20, y=y_pos)
        card.pack_propagate(False)

        lbl_title = tk.Label(card, text=title, font=("Arial", 9, "bold"), fg="#94a3b8", bg="#334155")
        lbl_title.pack(anchor="w", padx=12, pady=(10, 0))

        val_lbl = tk.Label(card, text=initial_val, font=("Arial", 18, "bold"), fg=color, bg="#334155")
        val_lbl.pack(anchor="w", padx=12, pady=(5, 10))
        setattr(self, attr_name, val_lbl)

    def start_serial_thread(self):
        threading.Thread(target=self.read_serial, daemon=True).start()

    def read_serial(self):
        global PORT
        while self.is_running:
            try:
                if not self.serial_conn or not self.serial_conn.is_open:
                    self.serial_conn = serial.Serial(PORT, BAUD, timeout=1)
                    self.root.after(0, lambda: self.status_label.config(text="Status: Connected", fg="#22c55e"))

                line = self.serial_conn.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    data = json.loads(line)
                    self.latest_data = data
                    self.data_queue.put(data)
            except Exception as e:
                self.root.after(0, lambda: self.status_label.config(text="Status: Disconnected / Port Error", fg="#ef4444"))
                time.sleep(2)

    def update_gui(self):
        try:
            redraw_needed = False
            while not self.data_queue.empty():
                data = self.data_queue.get_nowait()

                # Process Temperature with smoothing
                raw_temp = data.get("temp")
                if raw_temp is not None and raw_temp > -100:
                    smoothed_temp = self.smooth_temp(raw_temp)
                    self.temp_val.config(text=f"{smoothed_temp:.2f} °C")
                    data["temp"] = smoothed_temp

                # Process IR Oximeter Value
                ir = data.get("ir")
                if ir is not None:
                    self.ir_val.config(text=str(ir))

                # Process ECG Lead Status
                lead_p = data.get("lead_plus")
                lead_m = data.get("lead_minus")
                if lead_p == 1 or lead_m == 1:
                    self.lead_val.config(text="Lead Off!", fg="#ef4444")
                else:
                    self.lead_val.config(text="Connected", fg="#22c55e")

                # Evaluate Safety Guardrails & Trigger Alerts
                safety_status = self.evaluate_clinical_safety(data)
                if "ALERT" in safety_status:
                    self.alert_lbl.config(text=safety_status, fg="#ef4444")
                else:
                    self.alert_lbl.config(text=safety_status, fg="#22c55e")

                # Process ECG Waveform
                ecg = data.get("ecg")
                if ecg is not None:
                    self.ecg_data.pop(0)
                    self.ecg_data.append(ecg)
                    redraw_needed = True

            if redraw_needed:
                self.line.set_ydata(self.ecg_data)
                self.canvas.draw_idle()

        except queue.Empty:
            pass

        if self.is_running:
            self.root.after(30, self.update_gui)

    def on_close(self):
        self.is_running = False
        if self.serial_conn and self.serial_conn.is_open:
            try:
                self.serial_conn.close()
            except:
                pass
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = AINurseOriginalDashboard(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()