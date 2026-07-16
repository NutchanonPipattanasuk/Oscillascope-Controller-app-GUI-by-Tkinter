import tkinter as tk
import pyvisa
from tkinter import messagebox, filedialog
import time
import threading

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure



class OscillascopeController:

    def __init__(self):
        self.rm = pyvisa.ResourceManager('@py')
        self.inst = None

    def find_resource(self):
        try:
            return self.rm.list_resources('?*') #ค้นหาทุกพอร์ต
        except Exception:
            return []
        
    def connect(self, inst_name):
        if self.inst: #เช็คว่ามีการเชื่อต่อค้างอยู่มั้ย
            self.disconnect()

        try:
            self.inst = self.rm.open_resource(inst_name)
            self.inst.timeout = 5000

            try:
                self.inst.write("*CLS")
            
            except:
                pass

            return True, self.query("*IDN?") #ถ้าเชื่อมต่อสำเร็จจะ Return Tuple True และ ชื่อของ oscilloscope
        
        except Exception as e:
            return False, str(e) #ถ้าเชื่อมไม่สำเร็จจะ Return False และ error message

    def disconnect(self):
        if self.inst:
            self.inst.close()
            self.inst = None

    def write(self, command): #ส่งคำสั่งอย่างเดียว
        self.inst.write(command)

    def query(self, command): #ส่งคำสั่งไปและรับข้อความกลับมา
        return self.inst.query(command).strip() 
    
    def get_measurement(self, item, source):
        try:
            return self.query(f":MEASure:ITEM? {item},{source}")
        except Exception as e:
            return f"Error: {e}"
        
    def get_waveform(self, channel: int):
        ch = f"CHANnel{channel}"
        # 1. ตั้งค่าการดึงข้อมูล (บอกเครื่องว่าเราอยากได้อะไร)
        self.write(f":WAVeform:SOURce {ch}") # เลือกช่องสัญญาณ
        self.write(":WAVeform:FORMat BYTE")  # ขอข้อมูลในรูปแบบ BYTE (ตัวเลข 0-255)
        self.write(":WAVeform:POINts:MODE NORMal") 
        self.write(":WAVeform:POINts 1200") # ขอความละเอียด 1200 จุด
        # 2. ขอค่า Preamble (กุญแจถอดรหัส)
        # เครื่องจะส่งชุดตัวเลขบอกสเกลมา เช่น ระยะห่างของเวลาแต่ละจุด (xinc), ตัวคูณแรงดัน (yinc)
        preamble_str = self.query(":WAVeform:PREamble?")
        pre = [float(v) for v in preamble_str.split(',')]
        xinc, xor, xref = pre[4], pre[5], pre[6] # แกน X (สเกลเวลา)
        yinc, yor, yref = pre[7], pre[8], pre[9] # แกน Y (สเกลแรงดันไฟฟ้า)
        # 3. โหลดข้อมูลดิบ
        self.write(":WAVeform:DATA?")
        time.sleep(0.1) # รอเครื่องประมวลผล
        raw = self.inst.read_raw() # อ่านข้อมูลกลับมาทั้งหมด
        # 4. ตัดส่วนหัวทิ้ง
        # ข้อมูลดิบที่ส่งมาจะมี "ส่วนหัว" แปะมาด้วย เช่น "#800001200" เราต้องตัดมันทิ้งไปก่อน
        if raw[0:1] == b'#':
            n = int(chr(raw[1]))
            length = int(raw[2:2 + n])
            data = raw[2 + n: 2 + n + length] # เอาเฉพาะข้อมูลเนื้อๆ
        else:
            data = raw
        # 5. แปลงข้อมูลดิบให้เป็น เวลา(s) และ แรงดัน(V) ด้วยกุญแจถอดรหัสในข้อ 2
        times = [(i - xref) * xinc + xor for i in range(len(data))]
        voltages = [(b - yref) * yinc + yor for b in data]
        label = f"CH{channel}"
        return times, voltages, label # ส่งค่าแกน X, แกน Y และชื่อช่องสัญญาณ กลับไปให้คนเรียก
        
    
class GraphicUserInterface(tk.Tk):

    def __init__(self):
        
        super().__init__()
        self.controller = OscillascopeController()

        self.title("Oscillascope Controller")
        self.geometry("900x700")

        self.setup_ui()
        self.refresh_resource()

    def setup_ui(self): #Funcion ในการจัดการ UI

        #------ Connect Frame -----------------------------------------
        connect_frame = tk.Frame(self, bd=2, relief= tk.RAISED) #เป็น Frame ที่ใช้เก็บปุ่ม connect, disconnect, refresh และ dropdown ชื่อresource
        connect_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(connect_frame, text="VISA Resource:").grid(row=0, column=0, padx=5, pady=5)

        self.resource_var = tk.StringVar() #เก็บค่าว่าเลือกอะไรใน Dropdown
        self.resource_menu = tk.OptionMenu(connect_frame, self.resource_var, "")
        self.resource_menu.grid(row=0, column=1, padx=5, pady=5)

        self.btn_refresh = tk.Button(connect_frame, text="Refresh", command=self.refresh_resource) #ปุ่ม Refresh
        self.btn_refresh.grid(row=0, column=2, padx=5, pady=5)
        self.btn_connect = tk.Button(connect_frame, text="Connect", command=self.connect_instrument, bg="#00FF00", fg="#FFFFFF") #ปุ่มConnect
        self.btn_connect.grid(row=0, column=3, padx=5, pady=5)
        self.btn_disconnect = tk.Button(connect_frame, text="Disconnect", command=self.disconnect_instrument, state=tk.DISABLED, bg="#FF0000", fg="#FFFFFF") #ปุ่ม Dsiconnect ถูกปิดการใช้งานจะถูกเปิดก็ต่อเมื่อเชื่อต่อสำเร็จ
        self.btn_disconnect.grid(row=0, column=4, padx=5, pady=5)
        #--------------------------------------------------------------------------

        #----- Body Frame ----------------------------------------------
        body_frame = tk.Frame(self)
        body_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5) #ขยายตัวตามหน้าต่างโปรแกรม

        #----- Left Frame -------------------------------------------------
        left_frame = tk.Frame(body_frame) # กรอบฝั่งซ้าย 
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True) #เมื่อเหลือพื้นที่เหลือใน Body Frame ฝั่งซ้ายจะเป็นคนเอาไปเอง

        #----- CMD Frame ---------------------------------------------------
        cmd_frame = tk.Frame(left_frame, bd=2, relief= tk.SOLID)
        cmd_frame.pack(fill = tk.X, pady=5)

        tk.Label(cmd_frame,text="SCPI Command:").grid(row=0, column=0, padx=5, pady=5)

        self.cmd_entry = tk.Entry(cmd_frame, width=30)
        self.cmd_entry.grid(row=0, column=1, padx=5, pady=5)
        tk.Button(cmd_frame, text="Send", command=self.send_command).grid(row=0, column=2, padx=5, pady=5)
        #-------------------------------------------------------------------------

        #------ Measure Frame ------------------------------------------

        meas_frame = tk.Frame(left_frame, bd=2, relief=tk.SOLID)
        meas_frame.pack(fill=tk.X, pady=5)

        tk.Label(meas_frame, text="Channel:").grid(row=0, column=0, padx=5, pady=5)

        #Menu dropdown เลือก Channel
        self.chan_var = tk.StringVar(value="CHANel1")
        chan_opt = ["CHANnel1", "CHANnel2", "CHANnel3", "CHANnel4"]
        tk.OptionMenu(meas_frame, self.chan_var, *chan_opt).grid(row=0, column=1, padx=5, pady=5)

        #Menu Dropdown เลือก Measure option
        self.meas_var = tk.StringVar(value="VPP")
        meas_opts = ["VPP", "VMIN", "VMAX", "PERiod", "FREQuency"] 
        tk.OptionMenu(meas_frame, self.meas_var, *meas_opts).grid(row=0, column=3, padx=5, pady=5)

        # ปุ่มกดเพื่ออ่านค่า
        tk.Button(meas_frame, text="Read Value", command=self.read_measurement).grid(row=0, column=4, padx=5, pady=5)

        #-------------------------------------------------------------------------------

        #---- Waveform + SaveIMG Frame ----------------------------------------------------

        wave_frame = tk.Frame(left_frame, bd=2, relief=tk.SOLID)
        wave_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # Controls row
        ctrl_row = tk.Frame(wave_frame)
        ctrl_row.pack(fill=tk.X)

        tk.Label(ctrl_row, text="Channel:").grid(row=0, column=0, padx=5, pady=5)
        self.wave_chan_var = tk.StringVar(value="1")
        ch = ["1", "2", "3", "4"]
        tk.OptionMenu(ctrl_row, self.wave_chan_var, *ch).grid(row=0, column=1, padx=5, pady=5)
            

        self.btn_read_wave = tk.Button(ctrl_row, text="Read Waveform", command=self.read_waveform)
        self.btn_read_wave.grid(row=0, column=2, padx=5, pady=5)

        self.btn_save_image = tk.Button(ctrl_row, text="Save Image (PNG)", command=self.save_image, state=tk.DISABLED)
        self.btn_save_image.grid(row=0, column=3, padx=5, pady=5)

        # Matplotlib canvas
        self.fig = Figure(figsize=(5, 3), dpi=96)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor("#0d1117")
        self.fig.patch.set_facecolor("#161b22")
        self.ax.tick_params(colors="#c9d1d9")
        self.ax.spines["bottom"].set_color("#30363d")
        self.ax.spines["top"].set_color("#30363d")
        self.ax.spines["left"].set_color("#30363d")
        self.ax.spines["right"].set_color("#30363d")
        self.ax.set_xlabel("Time (s)", color="#8b949e")
        self.ax.set_ylabel("Voltage (V)", color="#8b949e")
        self.ax.set_title("No waveform yet", color="#8b949e")
        self.fig.tight_layout()

        self.canvas = FigureCanvasTkAgg(self.fig, master=wave_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))

        #--------------------------------------------------------------------------------

        #------------------------------------------------------------------------------

        #----- Right Frame : Console -------------------------------------------
        right_frame = tk.Frame(body_frame, width=350) # กรอบฝั่งขวา 
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=10)
        right_frame.pack_propagate(False) #ปิดระบบหด/ขยายตัวอัตโนมัติ

        tk.Label(right_frame, text="Console Output", font=("Helvetica", 10, "bold")).pack(pady=2)

        self.response_text = tk.Text(right_frame, wrap=tk.WORD, bg= "#F4F4F4") #สร้างกล่องข้อความ
        self.response_text.pack(fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(self.response_text)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y) #ชิดฝั่งขวาของกล่องข้อความ
        self.response_text.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.response_text.yview)

        tk.Button(right_frame, text="Clear Console", command=self.clear_response).pack(fill=tk.X, pady=5) #ปุ่ม Clear console
        #----------------------------------------------------------------------------

    #-------- Helper --------------------------------------------------------------
    def log(self, msg):
        self.response_text.insert(tk.END, msg + "\n") #พิมพ์ข้อความใหม่ต่อท้ายลงไปในกล่องข้อความ
        self.response_text.see(tk.END) #เลื่อนหน้าจอลงมาล่างสุดอัตโนมัติ

    def clear_response(self):
        self.response_text.delete(1.0, tk.END) # ลบข้อความทั้งหมดตั้งแต่ตัวอักษรแรกจนถึงตัวสุดท้าย (1.0หมายถึงบรรทัดที่ 1 ตัวอักษรที่ 0)

    def update_option_menu(self, menu, variable, options):
        menu['menu'].delete(0, 'end')
        for opt in options:
            menu['menu'].add_command(label=opt, command=tk._setit(variable, opt))
        variable.set(options[0] if options else "")
    #----------------------------------------------------------------------------------------

    #---- Connection -------------------------------------------------------------
    def refresh_resource(self):
        self.btn_refresh.config(state=tk.DISABLED) #ปิดปุ่มชั่วคราว
        self.log("Searching for VISA resources...")
        self.update_idletasks() #สั่งให้ UI อัพเดทข้อความบนจอทันที

        resources = self.controller.find_resource() #สั่งค้นหาพอร์ตและเก็บ List รายชื่อพอร์ตไว้

        self.update_option_menu(self.resource_menu, self.resource_var, list(resources)) #เอาพอร์ตที่หาเจอไปใส่ในเมนู Dropdown

        if resources:
            self.log(f"Found {len(resources)} resource(s).")
        else:
            self.log("No resources found.")

        self.btn_refresh.config(state=tk.NORMAL) #เปิดปุ่มอีกรอบ

    def connect_instrument(self):
        res = self.resource_var.get() #อ่านค่าพอร์ตจากเมนู Dropdown ว่าเลือกอันไหน
        if not res: #ถ้ายังไม่ได้เลือกพอร์ต
            messagebox.showwarning("Warning", "Please select a VISA resource.") #สร้างกล่องแจ้งเตือน
            return
            
        self.log(f"Connecting to {res}...")
        self.update_idletasks()
        
    
        success, msg = self.controller.connect(res) #สั่งเชื่อมต่อและคืนค่า True,False และ ชื่อรุ่นถ้าต่อสำเร็จ
        
        if success:
            self.log(f"Connected: {msg}")
            # ถ้าต่อสำเร็จ ให้ปิดปุ่ม Connect และเปิดปุ่ม Disconnect
            self.btn_connect.config(state=tk.DISABLED)
            self.btn_disconnect.config(state=tk.NORMAL)
        else:
            self.log("Connection failed.")
            messagebox.showerror("Error", f"Failed to connect:\n{msg}")

    def disconnect_instrument(self):
        self.controller.disconnect() 
        # สลับสถานะปุ่มกลับมาเหมือนเดิม
        self.btn_connect.config(state=tk.NORMAL)
        self.btn_disconnect.config(state=tk.DISABLED)
        self.log("Disconnected from instrument.")
    #------------------------------------------------------------------------------------------------------

    #---- SCPI -------------------------------------------------------------

    def send_command(self):
        cmd = self.cmd_entry.get().strip() #ดึงข้อความจากช่องพิมพ์

        if not cmd:
            return
        
        try:
            if '?' in cmd:
                self.log(f"> {cmd} (Query)") #พิมพ์บอกใน Console ว่ากำลังส่งคำสั่งถาม
                response = self.controller.query(cmd) #เรียกใช้ query 
                self.log(f"< {response}") #พิมพ์คำตอบที่ได้ลง Console
            else:
                self.log(f"> {cmd}") #ถ้าไม่มี '?' แสดงว่าเป็นคำสั่งสั่งการเฉยๆ
                self.controller.write(cmd) #เรียกใช้ write 

            self.cmd_entry.delete(0, tk.END) # เมื่อส่งเสร็จแล้วลบข้อความในช่องพิมพ์ทิ้งเพื่อเตรียมพิมพ์คำสั่งต่อไป

        except Exception as e:
            self.log(f"Error: {e}")

    #-----------------------------------------------------------------------------------

    #---- Measurement -------------------------------------------------

    def read_measurement(self):
        if not self.controller.inst: #เช็คว่าเชื่อมต่อเครื่องอยู่มั้ย
            messagebox.showwarning("Warning", "Not connected to an instrument.")
            return

        #ดึงค่าจาก Dropdown
        chan = self.chan_var.get() 
        meas = self.meas_var.get()

        self.log(f"Reading {meas} on {chan}...")
        self.update_idletasks()

        val = self.controller.get_measurement(meas, chan) 
        
        self.log(f"[{chan} - {meas}]: {val}") #ปริ้นต์ค่าที่อ่านได้ลง Console
    #-------------------------------------------------------------------------

    #---- Waveform -----------------------------------------------------------------

    def read_waveform(self):
        if not self.controller.inst:
            messagebox.showwarning("Warning", "Not connected to an instrument.")
            return

        ch = int(self.wave_chan_var.get())
        self.btn_read_wave.config(state=tk.DISABLED)
        self.log(f"Reading waveform from CH{ch}...")
        self.update_idletasks()

        def _do_read():
            try:
                times, volts, label = self.controller.get_waveform(ch)
                self.after(0, lambda: self._on_waveform(times, volts, label, None))
            except Exception as e:
                self.after(0, lambda err=e: self._on_waveform(None, None, None, err))

        threading.Thread(target=_do_read, daemon=True).start()

    def _on_waveform(self, times, volts, label, error):
        self.btn_read_wave.config(state=tk.NORMAL)
        if error:
            self.log(f"Waveform error: {error}")
            messagebox.showerror("Error", str(error))
            return

        self._times = times
        self._voltages = volts
        self._wave_label = label

        # Plot
        self.ax.clear()
        self.ax.set_facecolor("#0d1117")
        self.ax.tick_params(colors="#c9d1d9")
        for spine in self.ax.spines.values():
            spine.set_color("#30363d")

        self.ax.plot(times, volts, color="#58a6ff", linewidth=0.8, label=label)
        self.ax.set_xlabel("Time (s)", color="#8b949e")
        self.ax.set_ylabel("Voltage (V)", color="#8b949e")
        self.ax.set_title(f"Waveform — {label}  ({len(times)} points)", color="#c9d1d9")
        self.ax.legend(facecolor="#161b22", labelcolor="#c9d1d9", edgecolor="#30363d")
        self.ax.grid(True, color="#21262d", linewidth=0.5)
        self.fig.tight_layout()
        self.canvas.draw()

        self.btn_save_image.config(state=tk.NORMAL)
        self.log(f"Waveform read: {len(times)} points  ({label})")

    #---------------------------------------------------------------------------------

    #---- Waveform -----------------------------------------------------------------

    def save_image(self):
        if not self._times:
            return
        filepath = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("All files", "*.*")],
            title="Save Waveform as Image"
        )
        if filepath:
            try:
                self.fig.savefig(filepath, dpi=150, facecolor=self.fig.get_facecolor())
                self.log(f"Image saved: {filepath}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save Image:\n{e}")

    #---------------------------------------------------------------------------------


if __name__ == "__main__":
    app = GraphicUserInterface()
    app.mainloop()