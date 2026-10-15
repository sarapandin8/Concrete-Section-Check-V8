# IGIRDER.DOWEL32 — รูปช่วยกรอกระยะ U-dowel

ต่อจาก ZIP FLEXURE31 ที่ส่งมอบแล้ว โดยเพิ่มรูปตัดขวาง U-dowel และรูปขยายขอ 90° ในฟอร์ม Dowel detail

## วิธีเปิด

ใช้ Project JSON เดิม เช่น `I_Girder_20m_FLEXURE31_REVIEW.json` แล้วไปที่ Analysis → ULS Strength → Flexure → Final — Composite เปิด **Edit composite / dowel inputs** และขยาย **Dowel detail**

รูปอยู่เหนือช่องกรอก ใช้รหัส A–F ให้ตรงกัน ตัวเลขข้างรูปเปลี่ยนตามค่าที่แก้ไขโดยไม่ต้อง Calculate หากยังไม่ทราบระยะ รูปแสดง **Not entered** และช่องยังว่าง

| รหัส | ช่องกรอก | จุดวัด |
|---|---|---|
| A | U-leg centres a | ศูนย์กลางขา U สองขาในหน้าตัดขวาง ไม่ใช่ spacing ตามยาวคาน |
| B | Interface to outside of top hook | ระยะแนวดิ่งจากรอยต่อ girder–slab ถึงผิวนอกขอด้านบน |
| C | Straight tail after 90° bend | เริ่มจากจุดสัมผัสปลายโค้งถึงปลายเหล็ก ไม่นับส่วนโค้ง |
| D | Inside bend diameter | เส้นผ่านศูนย์กลางของวงกลมด้านในขอ ไม่ใช่รัศมี |
| E | Required clear cover | ระยะหุ้มที่ต้องการ วัดจากผิวคอนกรีตถึงผิวนอกเหล็ก |
| F | Straight bonded leg below interface | จากรอยต่อลงถึงจุดเริ่มส่วนโค้ง U ด้านล่าง ไม่นับส่วนโค้ง |

**How to measure A–F** แสดงคำอธิบายจุดวัดเพิ่มเติม ระยะทั้งหมดเป็น mm

## ขอบเขต

รูปเป็น schematic ไม่ได้เขียนตามสัดส่วนระยะที่กรอก และไม่ใช่หลักฐานยืนยันการวางเหล็กหรือการยึดเหนี่ยวจริง ตัวเลขเป็นข้อมูลที่ผู้ใช้ให้ ส่วนค่าระยะขั้นต่ำยังตรวจใน calculation review เดิม E ยังคงเริ่มจาก slab cover เดิมและแก้ไขได้ ค่าที่ไม่ทราบไม่มีการสมมติแทน

สูตรกำลังและ logic ULS/SLS ไม่เปลี่ยน แรง CSiBridge และการแปลงจุดอ้างอิงไม่เปลี่ยน Project JSON ใช้ schema เดิม ไม่มีการเพิ่มการบันทึก solver results รูปนี้ไม่เพิ่มกำลัง Tn หรือ composite V–T

## การตรวจสอบ

- py_compile ของ app.py และโมดูลที่แก้ไขผ่าน
- ชุดทดสอบที่เลือก 315 รายการผ่าน รวมการจับคู่ A–F, รักษาค่าว่าง, ป้องกันการแทรก markup และอัปเดตตัวเลขหลังแก้ไข มี 7 warnings เดิม ไม่ได้อ้างว่าทดสอบทั้ง repository
- เปิด app.py กับ JSON FLEXURE31 จริงใน Chromium 130 ตรวจที่ 1440 / 1280 px ป้ายระยะไม่ซ้อน ไม่พบ page error หรือ Streamlit exception
- เปิดรูปและคำอธิบายโดยไม่สั่งคำนวณ ยังมีปุ่ม Calculate Flexure เพียงปุ่มเดียว
- ภาพหน้าจอใช้ตรวจภายในเท่านั้น ไม่รวมใน ZIP หรือไฟล์ส่งมอบ

## Repo summary

```text
DOWEL32: Add U-dowel dimension guide A–F with live input labels and measurement endpoints; preserve calculations and JSON inputs.
```
