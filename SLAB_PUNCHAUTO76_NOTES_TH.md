# SLAB.PUNCHAUTO76 — อ่านข้อมูลโครงการและเลือกแนวทางตรวจอัตโนมัติ

หน้า Punching เริ่มจาก Automatic punching review โดยอ่านพื้นที่ลงแรงที่บันทึกไว้และ CSI load basis เดิม ผู้ใช้ไม่ต้องเริ่มจากการกรอกตาราง X/Y/L/B ที่ยังไม่ทราบ

| ข้อมูลโครงการ | การทำงานอัตโนมัติ | ขอบเขตผล |
|---|---|---|
| มี physical load areas บันทึกไว้ | ใช้พื้นที่เดิมทันที กด Calculate ได้โดยไม่กรอกหรือ Apply ซ้ำ | ใช้ตัวตรวจ Punching เดิม รวม geometry/material/steel และ scope guards เดิม |
| Equivalent train UDL และ source matched | อ่าน strip width และ ballast เดิม แสดงว่าเป็นโมเดลโหลดต่อเนื่อง พร้อมปุ่ม Review one-way shear | UDL ไม่ได้ระบุ footprint ของแรงล้อหรือแรงปฏิกิริยาเฉพาะที่; local punching ยัง NOT CALCULATED |
| UDL แต่ source changed / not recorded | แจ้งให้ทวน CSI load basis / Ballast เดิมแล้ว Calculate | ไม่ถือว่าคำประกาศโหลดตรงกับชุดไฟล์ใหม่โดยอัตโนมัติ |
| Imported forces ที่ไม่มี physical footprint | แสดงข้อมูลที่ยังไม่ระบุและพับตารางไว้ | ไม่เดาขนาดแรงกดจาก default width, จำนวน girder หรือ stress peaks |

ตาราง Punching load / reaction areas เป็น optional expander ที่พับไว้ กรอกเฉพาะเมื่อต้องตรวจแรงหรือ reaction เฉพาะที่ที่มีตำแหน่งและพื้นที่จริง การ Apply และการตรวจ input ยังใช้ PUNCH75 รวมการป้องกันแถวเพิ่ม/ลบซ้ำ

เมื่อไม่มีผล Punching จะไม่แสดงแผนที่สีเทาราวกับเป็นผลคำนวณแล้ว เมื่อมีพื้นที่และคำนวณสำเร็จ จะแสดงผลและเส้นรอบรูปเดิม

รายงาน Top slab เพิ่ม Punching_Automatic_Review.json ซึ่งอธิบาย route, source status และสถานะ local check จาก snapshot ของผลที่รายงาน ไม่อ่านค่า UI ล่าสุดหรือรัน solver ในรายงาน

## ข้อจำกัดของการทำอัตโนมัติ

รุ่นนี้ทำ input/scope review และใช้ข้อมูลที่มีอยู่ให้อัตโนมัติ ไม่ได้ย้อนหา actual load footprint จาก shell forces ไม่ได้สร้าง local wheel force จากค่า UDL และไม่ได้ถือว่า UDL เป็น code exemption ผล NOT CALCULATED ไม่ใช่ PASS หรือการรับรองว่าไม่ต้องตรวจ Punching ในโครงสร้างจริง

เอกสาร CSI SAFE อธิบายว่า automatic perimeter ใช้ข้อมูลตำแหน่งรับแรง และกรณี specified support/load size ใช้ขนาดพื้นที่ใน X/Y เพื่อสร้างเส้นรอบรูปตรวจ จึงต้องแยกการอ่าน geometry ที่มีอยู่จากการเดาขนาดพื้นที่ที่ไม่มีในข้อมูล:

https://docs.csiamerica.com/help-files/safe/Menus/Design/Punching_Check_Overwrites.htm

อ้างอิงนี้ประกอบการออกแบบ workflow ของข้อมูล ไม่ใช่การเปลี่ยน code basis ของตัวตรวจ AASHTO LRFD 2020 เดิม

## การรักษาผลเดิมและ QA

No engineering equations changed. No ULS/SLS calculation logic changed. No Project JSON schema changed. No additional result-cache persistence was added. PROJECT74 persistence และ COLOR73 palette คงเดิม

production changes จำกัดที่ derived assessment ใหม่, UI และการเพิ่ม assessment ลง report เท่านั้น ตรวจ AST ของ slab_top65.py ว่าต่างเฉพาะ report_zip; ฟังก์ชัน calculate/fingerprint/current และตัวตรวจ Punching64 เป็นของเดิม

ตรวจด้วย Streamlit AppTest ใน app.py จริง ครอบคลุม UDL ที่ source matched / changed, พื้นที่เดิมหลังเปิด JSON, ข้อมูลที่ไม่ระบุชนิดโหลด, การเปลี่ยน load basis ใน form, การไป One-way โดยไม่รัน solver ซ้ำ, report snapshot, PUNCH75 input transactions และ PROJECT74 round trip ดู SLAB_PUNCHAUTO76_VERIFICATION.json และ qa/evidence/slab_punchauto76/

หลักฐานการรันโครงการจริง 127,680 แถวใน PROJECT74 เป็น baseline; ไม่ได้รันโครงการนั้นซ้ำสำหรับ workflow patch นี้

ผลรอบ PUNCHAUTO76: targeted 46 กรณี และ regression 82 กรณี รวม 128 กรณีผ่านทั้งหมด; compile app.py และไฟล์ที่แก้/เพิ่มผ่าน ผลนี้เป็นการตรวจซอฟต์แวร์และ workflow ไม่ใช่การรับรองกำลังหรือยกเว้น Punching ของโครงสร้างจริง
