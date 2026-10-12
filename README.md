
# ClipWise AI QC (new project)

โปรแกรมใหม่ ไม่ต้องใช้ไฟล์ใดจาก Repository เก่า

## Deploy

1. GitHub: สร้าง repository ใหม่ เช่น `clipwise-ai-qc` และอัปโหลดไฟล์/โฟลเดอร์ทั้งหมดจาก ZIP (ไม่อัปโหลด ZIP เพียงไฟล์เดียว)
2. Streamlit Community Cloud: เลือก GitHub repo นี้ เลือก `app.py` แล้ว Deploy
3. ที่ App settings > Secrets (แนะนำ) ให้ตั้งค่า:

   ```toml
   GEMINI_API_KEY = "your_actual_API_key_here"
   ```

   อย่านำ API key ไปใส่ใน `app.py` หรือ Commit ลง GitHub

4. เลือกคลิปหลายไฟล์รวมไม่เกิน 120 MB ต่อชุด; กดเริ่มตรวจ ทำซ้ำเพื่อสะสมข้อมูลได้ถึง 1 GB ต่อรอบ (การอัปโหลดทีเดียว 1 GB บน Cloud ฟรีไม่รองรับอย่างรับประกัน)
5. ตรวจผลในตาราง ดาวน์โหลด `clipwise_results.csv`; กำหนดผลจริงด้วยตัวเองเพื่อโหลด `human_labels.csv` ไปวัดความแม่นยำ

## ข้อจำกัด

- Gemini API มีโควตา/ค่าใช้จ่ายตามบัญชี และไม่รวมใน Gemini Plus
- ต้องใช้ API key เพื่อให้วิเคราะห์คำพูดและภาพได้; ไม่มี key ทุกคลิปจะเป็น REVIEW
- ยังไม่มีการทดสอบความแม่นยำจากมนุษย์หรือเวลาครบทุกขั้นบน Community Cloud
- โมเดลอาจพลาดช็อตผิดเพียงเฟรมเดียว (Gemini เริ่มจากการสุ่มภาพวิดีโอราว 1 FPS)
- ผลเซสชันหายได้เมื่อ Cloud รีสตาร์ต; ดาวน์โหลด CSV ไว้เสมอ
- ส่งคลิปไปยัง Gemini API เมื่อเปิดวิเคราะห์ด้วย key: ตรวจสิทธิ์/ความเป็นส่วนตัวของคลิปก่อนใช้

## Files

- `app.py` หน้าเว็บ
- `qc_engine.py` ตรวจและตัดสิน
- `requirements.txt`, `packages.txt`, `.streamlit/config.toml` ตั้งค่า
- `catalog_example.csv` ตารางสินค้าอ้างอิง
- `tests/test_engine.py` ชุดทดสอบพื้นฐาน
