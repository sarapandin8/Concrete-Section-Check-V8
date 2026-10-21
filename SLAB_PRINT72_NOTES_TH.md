# SLAB.PRINT72 — แนว I-girder / bearing และกราฟโทนอ่อนสำหรับพิมพ์

พัฒนาต่อจาก ANALYSIS.QA71 โดยเปลี่ยนเฉพาะการแสดงผลหน้า Slab Reinforcement ไม่เพิ่มข้อมูลที่ผู้ใช้ต้องกรอก

- Plan map ทุก Result แสดงแนว I-girder พร้อม G1, G2, … และพิกัด Y สำหรับแนวคานขนาน Global X ชื่อ G เป็นลำดับอ้างอิงตาม connection layout ที่นำเข้า เช่นเดียวกับ support references เดิม ไม่ใช่การตั้งชื่อ CSI Girder Type ใหม่ Hover ที่ป้ายแสดง native frame IDs
- แสดงแนว bearing จาก offsets และชนิดจุดอ้างอิงที่ยืนยันไว้ในโครงการ พร้อมสัญลักษณ์โปร่งที่จุดตัดกับคาน ข้อมูลที่เป็น inside face ยังคงเรียก inside face ไม่เปลี่ยนเป็น CL; ถ้าข้อมูลไม่ยืนยัน แอปไม่เดาว่า bearing อยู่ที่ปลายสะพาน
- สัญลักษณ์ bearing เป็นจุดอ้างอิง ไม่ใช่รูปขนาดจริงหรือพื้นที่ bearing เมื่อไม่มีข้อมูลความยาว
- Station D/C แสดง bearing ตามระยะจริง และมีรายการพิกัด I-girder ใต้กราฟ โดยไม่เอาพิกัด Y ไปวาดเป็นค่าบนแกน D/C
- แผนที่ใช้ฟ้าอ่อน / ครีม / ชมพูอ่อนบนพื้นขาว ตัวอักษรยังเข้ม สีแดงและสเกล D/C ยังคงแยกค่าที่เกิน 1.0 พื้นที่ excluded / unresolved เป็นเทาอ่อน ค่าที่หายไม่ถูกแทนด้วยศูนย์
- กดไอคอนกล้องของกราฟหลักหรือ Punching เพื่อดาวน์โหลด **SVG** ที่ขยายและพิมพ์ได้คมชัด ค่าเริ่มต้นของ export คือ 1440 × 780 ป้ายและ legend ยึดกับพื้นที่รูปเพื่อไม่ตกขอบเมื่อส่งออก

ใน JSON32 และ CSI exports เดิม พบ I-girder 6 แนว: G1–G6 อยู่ที่ Y = +3.70, +2.50, +1.30, −1.30, −2.50, −3.70 ม. ตามลำดับ และ bearing CL อยู่ที่ s = 0.40 / 19.60 ม. มีจุดอ้างอิงตัดคาน 12 จุด ค่าเหล่านี้ใช้เป็นตัวอย่าง QA; โค้ดแสดงตำแหน่งจากข้อมูลจริงของแต่ละโครงการ ไม่ได้ hard-code ระยะหรือจำนวนคาน

ตรวจจากข้อมูลจริงครบ 10 Result × Plan/Station = 20 รูป และทวน 7 CSV เชิงตัวเลขเทียบ accepted QA71 แบบ byte-for-byte ผลตรงกัน ทั้ง 8 native shell components, record keys และ exclusions เดิมคงอยู่ ไม่มีการแก้กำลังหน้าตัด แกนแรง สมการ AASHTO หรือสถานะการยอมรับงานออกแบบ

ชั้นแสดงผลเดียวกันใช้กับ plan maps ใน case studies และ Punching ด้วย ตัวแบบคำนวณยังเป็น SLAB.REVIEW68; print milestone ไม่ทำให้ REVIEW กลายเป็น PASS และไม่เพิ่ม result persistence

หลักฐานอยู่ใน `SLAB_PRINT72_VERIFICATION.json` และ `qa/evidence/slab_print72/` ตัวช่วยตรวจซ้ำ:

```bash
python qa/slab_print72_real_inputs.py --project PROJECT.json --exports FORCES.xlsx AREAS.xlsx ASSIGNMENTS.xlsx CONNECTIVITY.xlsx --output /tmp/slab72-real
python qa/slab_print72_render_verify.py --figures /tmp/slab72-real/figures --output /tmp/slab72-render
python qa/slab_print72_browser_verify.py --project PROJECT.json --exports FORCES.xlsx AREAS.xlsx ASSIGNMENTS.xlsx CONNECTIVITY.xlsx --output /tmp/slab72-browser
```
