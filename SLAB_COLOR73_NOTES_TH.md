# SLAB.COLOR73 — สีสดและเข้มขึ้นระดับกลาง

ปรับจาก PRINT72 ตามผลตอบรับว่าสีจางเกินไป โดยเพิ่มความอิ่มสีของแผนที่เป็นฟ้า–เทอร์ควอยซ์ระดับกลาง ใช้เหลืองทองเมื่อเข้าใกล้ D/C = 1 และชมพู–แดงสำหรับค่าที่เกินเกณฑ์ เส้นกราฟ Station D/C เป็นสีน้ำเงินที่เข้มขึ้น พื้นรูปยังเป็นสีขาว พื้นที่ excluded / unresolved และตำแหน่ง I-girder / bearing ใช้รูปแบบเดิม

ไม่เพิ่มตัวเลือกหรือช่องกรอกใหม่ ไม่เปลี่ยนสมการ สเกล D/C จุดอ้างอิงแรง ผลคำนวณ geometry หรือตำแหน่งป้าย การส่งออกด้วยไอคอนกล้องยังเป็น SVG ตาม PRINT72 ชื่อรุ่นภายในของ shared print layout ยังคง PRINT72 เพื่อใช้กติกา layout/readability เดิม; palette revision คือ COLOR73

รอบนี้แก้ production code เพียงค่าคงที่สี 7 ค่าใน `visualization/slab_print72.py` ตรวจ AST ว่าโค้ดทำงานและค่าคงที่อื่นไม่เปลี่ยน และเทียบไฟล์ production ที่เหลือกับ ZIP baseline โดยตรง

ทวนรูปจาก native-data figures ที่ผ่านการตรวจใน PRINT72 จำนวน 20 รูป เปลี่ยนเฉพาะสี แล้วตรวจว่า fields อื่นทั้งหมด รวมถึงพิกัด ตัวเลข D/C ข้อมูลสเกลสี และ annotations เหมือนเดิม ไม่รัน structural solver ซ้ำเพื่อเปลี่ยนสี เอกสารผลทดสอบ 279 กรณีใน PRINT72 เป็นหลักฐานของ baseline ไม่ใช่จำนวน tests ที่รันใหม่ในรอบนี้

ดู `SLAB_COLOR73_VERIFICATION.json` และ `qa/evidence/slab_color73/` สำหรับหลักฐานสีและความคงเดิมของข้อมูล

ตรวจ regression เดิมเฉพาะ global readability ผ่าน 5 กรณี ไม่รันกรณี structural calculation ซ้ำ และ compile `app.py` พร้อมไฟล์ที่แก้/เพิ่มผ่าน

การตรวจ print references และ colour scale ในรอบนี้ใช้การเทียบ native figures และ AST; ไม่ได้รันชุด print72 tests เพราะ fixtures นำเข้า Streamlit testing runtime ซึ่งไม่ได้ติดตั้งในสภาพแวดล้อมนี้

ทำซ้ำการตรวจรูปด้วย `python qa/slab_color73_preview.py --source qa/evidence/slab_color73/print72_native_figures --output /tmp/slab_color73_preview` โดยใช้ Plotly 5.24.1 และ Kaleido 0.2.1
