# REPORT.RUNTIME83 — แก้ภาระการเปิดหน้า Report / QA

ต่อจาก concrete-section-pro_REPORT-ALL82.zip (SHA-256 2686fedf39f575d7ef353618d0ab2e5d98af8b05302152c41e990fc1c90cc8c5)

## สิ่งที่ยืนยันจาก log และโค้ด

log ที่แนบไม่พบ Python traceback ของ fatal error หรือข้อความ OOM/Killed โดยตรง มี warning ของ use_container_width, widget state และ DataFrame fragmentation จึงยังสรุปไม่ได้ว่า process บน Cloud หยุดเพราะเหตุใดแน่นอน ภาพ Oh no ร่วมกับ log ที่ไม่มี fatal exception สอดคล้องกับอาการทรัพยากรเกินตามคำอธิบายของ Streamlit แต่เป็นข้อสันนิษฐาน ไม่ใช่หลักฐานยืนยัน OOM

ข้อบกพร่องที่ทดสอบซ้ำได้ใน ALL82 คือการเปิดหน้า Report / QA สร้าง CalculationReport ทั้งชุด พร้อมรายละเอียดตารางและกราฟ ULS แม้ส่วน preview/review/traces ถูกยุบอยู่ st.expander แบบเดิมซ่อนเฉพาะหน้าจอ แต่ยังประมวลผลด้านใน จึงเพิ่มภาระหลัง Analysis สะสมข้อมูลไว้แล้ว

## สิ่งที่แก้

- เปิดหน้า Report / QA โดยไม่สร้าง CalculationReport, Word, PNG หรือกราฟล่วงหน้า
- Preview, Engineering review, Calculation traces และ ULS chart panel ใช้ tracked expanders และทำงานเมื่อเปิดจริง
- กด Create complete Word report ครั้งเดียวจึงสร้างรายงานครบทุกบท สมการ รูปหน้าตัด กราฟ และภาคผนวกตาม ALL82 ไม่เพิ่มตัวเลือกเนื้อหาหรือช่องยืนยัน
- ตรวจ currency ของไฟล์ที่สร้างไว้เพียงครั้งเดียวต่อ rerun และไม่สั่ง rerun ซ้ำหลังสร้างสำเร็จ
- ปลดไฟล์ export เก่าก่อนสร้างทดแทน และไม่ปล่อยไฟล์ทดแทนที่ล้มเหลวเป็น complete download
- hash JSON แบบ incremental โดยคง digest และการตรวจทุก cell ตามเดิม ลดการสร้างสำเนาข้อความ JSON/UTF-8 ทั้งก้อน
- จับข้อผิดพลาดตอนเตรียมรายงาน ตรวจ currency และ preview ที่ขอบเขต UI พร้อมบันทึก traceback แทนการปล่อย exception ทำให้หน้าหยุด
- Preview แสดงไม่เกิน 200 แถวต่อตาราง พร้อมแจ้งจำนวนแถวเต็ม Word และ evidence ยังคงครบทุกแถว
- หน้า Report เป็น read-only จึงไม่ refresh sidebar currency ซ้ำท้ายรอบ ไม่มี solver ใดถูกเรียกเพื่อเติมผลที่ขาด

## รูปแบบและข้อมูลเดิม

Word ใช้แม่แบบ BG40 R10 เดิมทุก workflow ข้อมูล ค่าคำนวณ สมการ กราฟ และสถานะ FAIL/REVIEW/STALE ไม่ถูกปรับให้ผ่าน หมายเลขรูปแบบเอกสารยังเป็น REPORT.ALL82 เพราะ patch นี้แก้ runtime และ UI เท่านั้น

ไม่มีการแก้ engineering kernels, Project JSON หรือ result-cache persistence ไม่เปลี่ยน requirements จาก ALL82

## ผลตรวจ

ดู RELEASE_REPORT_RUNTIME83.json และ qa/evidence/report_runtime83/ สำหรับผล regression, native download และการวัดหน้าแรก ข้อมูล benchmark เป็นตัวอย่างสมมติเดิมบนเครื่องทดสอบ ไม่ใช่การวัดหน่วยความจำของ Cloud จริง และค่า peak RSS ระบุเฉพาะ process แอป ไม่รวม subprocess ของ native renderer

log Cloud ใช้ Python 3.14.10 / pandas 3.1.0 ส่วนชุดทดสอบนี้ใช้ Python 3.12.14 / pandas 2.2.3 กับ Streamlit 1.61.0, Plotly 5.24.1 และ Kaleido 0.2.1 จึงไม่ได้อ้างว่าทดสอบตรง environment Cloud ทุกส่วน หรือยืนยันสาเหตุการหยุดของ Cloud ได้แล้ว

## ติดตั้ง

นำเนื้อหาในโฟลเดอร์ concrete-section-pro ของ ZIP ไปแทนไฟล์ใน repository ที่ Streamlit ใช้งาน แล้ว Reboot app จาก Manage app หลังอัปเดตโค้ด โหลด project และคำนวณ Analysis ตามขั้นตอนเดิม จากนั้นเปิด Report / QA และกด Create complete Word report

ไฟล์นี้ไม่ได้ deploy หรือ reboot live app ให้อัตโนมัติ ผล Analysis ใน session ไม่ได้เพิ่มการบันทึกถาวร ควรเก็บ project inputs ก่อน reboot หาก session เดิมยังเปิดได้

## แหล่งอ้างอิงพฤติกรรม Streamlit

- https://docs.streamlit.io/develop/api-reference/layout/st.expander
- https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app
