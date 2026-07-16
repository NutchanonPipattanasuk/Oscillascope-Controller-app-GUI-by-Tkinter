import tkinter as tk
import pyvisa
from tkinter import messagebox, filedialog
import time


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

        meas_frame = tk.Frame(left_frame, bd=2, relief=tk.GROOVE)
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


if __name__ == "__main__":
    app = GraphicUserInterface()
    app.mainloop()