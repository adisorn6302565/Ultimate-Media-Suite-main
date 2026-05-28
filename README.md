# 🚀 Ultimate Media Suite v1.3.2

**Ultimate Media Suite** คือแอปพลิเคชันเดสก์ท็อปสำหรับดาวน์โหลดและแปลงไฟล์มีเดีย (วิดีโอ/เสียง/ภาพ) ที่ผมพัฒนาขึ้นเพื่อใช้งานจริง โดยเน้นความเรียบง่าย สวยงาม และใช้งานได้ทันทีโดยไม่ต้องติดตั้ง (Portable) 

โปรแกรมนี้ใช้ `yt-dlp` และ `FFmpeg` เป็นแกนหลัก ทำงานผ่าน GUI ที่ทันสมัย รองรับ Dark Mode มีระบบคิวดาวน์โหลดแบบขนาน ดึงคุกกี้จากเบราว์เซอร์ได้ และรองรับการเร่งความเร็วด้วย GPU ครบทุกค่าย (NVIDIA, Intel, AMD)

---

## 🛠️ Tech Stack & Dependencies

* **Language**: Python 3.14+
* **GUI**: CustomTkinter (ธีมมืดสวยงามสไตล์ Modern ตอบโจทย์การใช้งานระยะยาว)
* **Core Engines**:
  * `yt-dlp`: ดาวน์โหลดสตรีมจากแพลตฟอร์มต่างๆ
  * `FFmpeg` / `FFprobe`: ประมวลผลและแปลงไฟล์มีเดีย
* **Key Libraries**:
  * `concurrent.futures` / `threading`: จัดการคิวและดาวน์โหลดแบบขนาน
  * `Pillow`: ประมวลผล Thumbnail สำหรับพรีวิว
  * `subprocess`: เชื่อมต่อกับ External Tools
  * `uv`: จัดการ Environment และ Dependencies ให้เร็วและสะอาด
* **Packaging**: `PyInstaller` (Build เป็น Single-file Portable Executable)

---

## 🌟 Key Features

### 📥 High-Speed Stream Downloader
* **รองรับหลายแพลตฟอร์ม**: YouTube, Facebook, Instagram, TikTok และอื่นๆ ผ่าน yt-dlp
* **คุณภาพสูงสุด**: ดาวน์โหลดได้ถึง **4K** พร้อมรวม Video/Audio อัตโนมัติ หรือแยกเสียงเป็น **MP3 (320kbps)** / **WAV** พร้อม Tags ครบถ้วน
* **จัดระเบียบไฟล์อัตโนมัติ**: แยกโฟลเดอร์ตาม Channel Name และตั้งชื่อไฟล์เป็นลำดับเรียบร้อย
* **ไม่ค้าง ไม่หน่วง**: สแกนข้อมูลวิดีโอแบบ Asynchronous UI ไม่ฟรีซขณะประมวลผลลิงก์
* **Batch Download**: รองรับ Playlist และหน้า Profile ทั้งหมด
* **Browser Cookies**: ดึงคุกกี้จาก Chrome, Edge, Firefox, Brave, Opera, Vivaldi, Safari เพื่อเข้าถึงวิดีโอ Private หรือ Age-restricted

### 🔄 GPU-Accelerated Converter
* **รองรับหลายฟอร์แมต**: MP4, MKV, MP3, WAV, GIF, FLAC, AAC, WEBM
* **ตรวจจับ GPU อัตโนมัติ**: ตรวจสอบครั้งเดียวตอนเปิดโปรแกรม แล้วแคชผลลัพธ์ไว้ รองรับ:
  * **NVIDIA**: `h264_nvenc`
  * **Intel Quick Sync**: `h264_qsv`
  * **AMD**: `h264_amf`
* **CPU Fallback**: หากไม่มี GPU ที่รองรับ จะสลับไปใช้ `libx264` + `aac` อัตโนมัติ เพื่อให้มั่นใจว่าแปลงไฟล์ได้เสมอ
* **Quality Presets**: เลือกได้ 3 ระดับ (Ultra CRF 18, Normal CRF 23, Small CRF 28)

### ⚙️ Settings & Configuration
* **Parallel Downloads**: ปรับจำนวน Thread ได้ตั้งแต่ 1–10 ตามความเร็วเน็ต
* **Custom Output Path**: กำหนดโฟลเดอร์เก็บไฟล์ได้ตามต้องการ
* **One-click Update**: อัปเดต yt-dlp เวอร์ชันล่าสุดได้ง่ายๆ ป้องกันลิงก์เสียเมื่อแพลตฟอร์มเปลี่ยน API

---

## 📂 Project Structure

```
├── .venv/                         # สภาพแวดล้อมจำลอง (Virtual Environment)
├── bin/                           # ไฟล์ไบนารีระบบ (ffmpeg.exe, ffprobe.exe, yt-dlp.exe)
├── dist/                          # โฟลเดอร์ปลายทางสำหรับการแจกจ่ายโปรแกรมที่บิลด์สำเร็จ
│   └── Ultimate Media Suite.exe   # ตัวรันแอปพลิเคชันแบบเดี่ยว (Standalone Executable)
├── logo.ico                       # ไฟล์ไอคอนโปรแกรม
├── main.py                        # ซอร์สโค้ดหลักของแอปพลิเคชัน
├── requirements.txt               # รายการไลบรารีที่จำเป็น
├── settings.json                  # ไฟล์เก็บการตั้งค่าของผู้ใช้
├── Ultimate Media Suite.spec      # ไฟล์ตั้งค่าการบิลด์ของ PyInstaller
└── build.bat                      # สคริปต์สั้นอัตโนมัติสำหรับการล้างและบิลด์ใหม่
```

---

## 💡 Behind the Scenes: ปัญหาที่เจอและวิธีแก้

ส่วนนี้คือสิ่งที่ผมได้เรียนรู้ระหว่างพัฒนาโปรเจกต์นี้ครับ:

### 1. แก้ปัญหา Network Bottleneck & HTTP 403
* **ปัญหา**: เมื่อดาวน์โหลด Playlist ใหญ่ (50+ คลิป) การดึง Thumbnail พร้อมกันทั้งหมดทำให้พอร์ตเครือข่ายเต็ม แอปค้าง และโดน Server บล็อก (403 Forbidden)
* **วิธีแก้**: ใช้ `ThreadPoolExecutor(max_workers=4)` จำกัดการดึงรูปพร้อมกันไม่เกิน 4 รูป
* **สิ่งที่ได้เรียนรู้**: การจัดการ Resource, Thread Pool และความสำคัญของ Rate-Limiting เมื่อทำงานกับ External API

### 2. ลด Latency ด้วยการ Cache ผลตรวจ GPU
* **ปัญหา**: เดิมทีรัน `ffmpeg -encoders` ทุกครั้งที่กดแปลงไฟล์ ทำให้หน่วง 300–800ms ต่อไฟล์
* **วิธีแก้**: ตรวจเช็ค Encoder ที่รองรับเพียงครั้งเดียวตอนเปิดโปรแกรม แล้วเก็บผลลัพธ์ไว้ใน `self.supported_encoders`
* **สิ่งที่ได้เรียนรู้**: การ Cache ข้อมูลระบบและการ Optimize Latency ส่งผลต่อ UX มากแค่ไหน

### 3. รองรับ GPU ข้ามค่ายอย่างแท้จริง
* **ปัญหา**: เดิมรองรับแค่ NVIDIA NVENC คนใช้ Intel/AMD แปลงไฟล์เร็วไม่ได้
* **วิธีแก้**: เขียนระบบตรวจจับ GPU แบบยืดหยุ่น รองรับ `h264_qsv` (Intel) และ `h264_amf` (AMD) พร้อมปรับ Parameter (`global_quality`, `qp`, `cq`) ให้ตรงกับสถาปัตยกรรมแต่ละค่าย
* **สิ่งที่ได้เรียนรู้**: การออกแบบระบบให้ Compatible กับ Hardware ที่หลากหลาย และเข้าใจ Multimedia Encoding Parameters ลึกขึ้น

### 4. จัดการ Path ใน PyInstaller Single-file
* **ปัญหา**: เมื่อ Build เป็นไฟล์เดี่ยว โปรแกรมหา `ffmpeg.exe` / `yt-dlp.exe` ไม่เจอ เพราะ Path ชี้ไปผิดที่
* **วิธีแก้**: สร้างฟังก์ชัน `resource_path()` ที่ชี้ไป `sys._MEIPASS` เมื่อรันในรูปแบบ Compiled
* **สิ่งที่ได้เรียนรู้**: การทำงานของ Sandbox Environment และการจัดการ Absolute Path ใน Distributed Desktop App

---

## ⚙️ Installation & How to Run

### Prerequisites
ตรวจสอบว่ามี `ffmpeg.exe`, `ffprobe.exe`, `yt-dlp.exe` อยู่ในโฟลเดอร์ `bin/` หรือเพิ่มเข้า System PATH แล้ว

### Development Setup (แนะนำใช้ uv)
```bash
# คัดลอกโฟลเดอร์และเปิดเข้าไปในไดเรกทอรี
cd -Ultimate-Media-Suite-main

# สร้างสภาพแวดล้อมจำลองและติดตั้งความต้องการอัตโนมัติ
uv venv
uv pip install -r requirements.txt

# รันเริ่มโปรแกรมได้ทันที
uv run python main.py
```

### หรือใช้ Python มาตรฐาน:
```bash
# สร้างสภาพแวดล้อมจำลอง
python -m venv .venv
.venv\Scripts\activate

# ติดตั้งไลบรารีที่จำเป็น
pip install -r requirements.txt

# รันแอปพลิเคชัน
python main.py
```

### Build เป็น Standalone Executable
```bash
.\build.bat
```
ไฟล์ที่ได้จะอยู่ที่ `dist/Ultimate Media Suite.exe`

---

## 🛡️ License & Credits

* พัฒนาโดย **คานาโอะ**
* ขอขอบคุณทีมพัฒนา `yt-dlp`, `FFmpeg` และ `customtkinter` ที่ทำให้โปรเจกต์นี้เป็นไปได้
* เผยแพร่ภายใต้ **MIT License** ดูรายละเอียดในไฟล์ `LICENSE`
