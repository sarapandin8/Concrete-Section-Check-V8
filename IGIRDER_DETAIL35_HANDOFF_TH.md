# IGIRDER.DETAIL35 — Auto dowel bend / slab mesh inputs

รุ่นนี้ปรับข้อมูลรอยต่อและเหล็กพื้นบน–ล่างให้ตรงความหมาย ก่อนพัฒนากลไก composite V–T ต่อจาก COUPLED34

## สิ่งที่แก้

- D เป็นเส้นผ่านศูนย์กลางด้านในของส่วนดัด คำนวณอัตโนมัติ 6.0db จากขนาด U-dowel ของโซนที่ใช้จริง เช่น DB12 → 72 มม.; ถ้าขนาดเปลี่ยน โปรแกรมคำนวณใหม่ที่สถานีนั้น ไม่เลือกขนาดจากตาราง dowel ที่ไม่ได้ใช้งาน
- D ที่คำนวณเป็นขนาดกำหนดสำหรับออกแบบ ต้องตรวจเทียบเกณฑ์รัศมีดัด/เส้นผ่านศูนย์กลางดัดของ code อีกครั้ง ขนาดใหญ่ที่เกณฑ์ทั่วไปต้องการ 8db จะไม่ถูกยอมให้ผ่านด้วย 6db
- E เป็นระยะวัดจากผิวบนพื้นถึงผิวนอก hook; B คำนวณจาก Tslab − E ไม่ต้องกรอกซ้ำ
- แยก cover ขั้นต่ำของ girder และ slab ออกจาก E; ไม่ใช้ E เป็น cover ด้านข้าง web
- ตารางหลักเหลือ A, C, E, F; มีรูปประกอบ A–F ตรงกับความหมายใหม่ และช่องขั้นสูงสำหรับ cover / D ที่วัดจริง
- เพิ่ม Slab mesh — top / bottom, both directions: แสดงเหล็กตามยาวที่มีอยู่แล้ว และรับเฉพาะเหล็กตามขวางบน–ล่างที่ยังขาด
- ตารางตามขวางรับขนาด ระยะเรียง clear cover ของเหล็กเส้นนั้น และ fy; เริ่ม fy จากเหล็กพื้นชั้นเดียวกันที่มีข้อมูลอยู่และแก้ได้ถ้าเป็นคนละเกรด ไม่คัดลอก cover ของเหล็กอีกทิศมาเป็นตำแหน่งจริง
- บันทึกเฉพาะ input ใน JSON; การกรอก/ทบทวนตารางไม่เรียก solver และไม่เพิ่มปุ่ม Calculate
- เมื่อข้อมูล U-detail เปลี่ยน ผล research เดิมเป็น stale; hash ผล Flexure/Interface ที่ไม่ได้ใช้รายละเอียดนี้ยังแยกจากกัน

## ใช้งานที่ไหน

Analysis → ULS Strength → Flexure → Final — Composite → Edit composite / dowel inputs

1. Dowel detail — saved dimensions: ดู/แก้ A, C, E, F และดู B, D ที่คำนวณ
2. Slab mesh — top / bottom, both directions: กรอกเหล็กตามขวางบน–ล่าง ส่วนตามยาวแก้ที่ Section Builder ตามเดิม
3. ใช้ Calculate Flexure ปุ่มหลักเมื่อต้องการคำนวณตามขอบเขตเดิม

## JSON โครงการ 31 ที่ปรับตามคำยืนยันของผู้ใช้

- E = 170 มม., Tslab = 350 มม. → B = 180 มม.
- D อัตโนมัติ 6.0db; ขนาด dowel ที่เลือกปัจจุบัน DB12 → D = 72 มม.
- ใช้ cover ขั้นต่ำเดิมของโครงการ: girder 40 มม. จาก torsion settings; slab 50 มม. จาก slab cover
- เก็บค่ารายละเอียดเก่าไว้ใน legacy_detail35 เพื่ออธิบายการย้ายข้อมูล
- ไม่แก้แรง CSiBridge, หน้าตัด, เหล็กตามยาว, prestress, ระยะเรียง dowel หรือ zoning
- เหล็กพื้นตามขวางยังว่าง; ไม่ตีความป้ายในภาพเป็นทิศทาง/ตำแหน่งเหล็กโดยอัตโนมัติ

JSON เก่าทั่วไป: E เดิมหมายถึง cover ขั้นต่ำ จึงเก็บความหมายเดิมไว้ใน cover requirements; ระดับ hook ใหม่หาได้เฉพาะจาก B ที่เคยบันทึก ไม่เดาจากขนาดของ E เดิม มีข้อความอธิบายเมื่อเปิด input เดิม

## ข้อที่ยังต้องตรวจจากรายละเอียดจริง

สำหรับ DB12, fy 390 MPa, slab fc 35 MPa, girder fc 45 MPa, normal weight และไม่ใช้ตัวคูณลดที่ต้องอาศัยข้อมูล confinement/cover เพิ่มเติม:

- B 180 มม. ยังน้อยกว่า hook development ที่แนวตรวจทั่วไปคำนวณประมาณ 190.803 มม.; D 72 มม. ไม่ได้แก้ปัญหา development นี้
- web 200 มม., ระยะศูนย์ขา 120 มม., db 12 มม. → clear cover ด้านข้าง (200−120−12)/2 = 34 มม. เทียบกับค่าโครงการ 40 มม.; ระบบคงผลไม่ผ่านด้านนี้ไว้ ไม่แก้ระยะขา A ให้เอง
- การผ่านการตรวจมิติไม่ได้ยืนยัน splitting, concrete struts/nodes, bond/slip compatibility หรือวงปิด torsion ของระบบจริง
- ข้อมูลเหล็กตะแกรงใหม่เป็น input inventory และพื้นที่เหล็กต่อเมตร ไม่เพิ่ม Mn ตามยาว ไม่แทน closing bar ของ research model และไม่เพิ่ม Full composite Tn / V–T โดยอัตโนมัติ
- COUPLED34 ยังเป็น research model; production Full composite Tn / V–T ยัง WITHHELD

ฐานเกณฑ์ anchorage: เอกสาร AASHTO LRFD 9th Edition (2020), ข้อ 5.10.2.1, 5.10.2.3, 5.10.8.2.1a, 5.10.8.2.4a และ 5.10.8.2.6d ที่ผู้ใช้ให้มา

## การตรวจสอบซอฟต์แวร์

ผลการทดสอบฉบับสุดท้ายและรายละเอียด package ดู release record ท้ายเอกสารและ qa/evidence/igird_detail35 ใน ZIP

Browser QA ใช้ app.py จริง ที่ความกว้าง 1440 และ 1280 พิกเซล: แก้ตาราง 4 ครั้งต่อเนื่อง ค่าเดิมไม่หาย แผง input ไม่ปิด JSON ตรงกับค่าหน้าจอ แรงเดิมไม่เปลี่ยน และ solver ถูกเรียก 0 ครั้งระหว่างกรอก ไม่มี browser error ค่าเหล็กที่ใช้ทดสอบเป็น QA เท่านั้น ไม่ถูกใส่ใน JSON ส่งมอบ

การทดสอบเหล่านี้ยืนยันพฤติกรรมซอฟต์แวร์และการแปลความหมาย input ไม่ใช่ structural validation ของ Full composite resistance

## Repo summary

Automate zone-specific dowel bends at 6db, separate hook top depth from minimum covers, and add independent top/bottom transverse slab-mesh inputs while reusing longitudinal data. Preserve legacy input meaning, stable table editing and research-only resistance scope.

## Final release checks

- Selected regression/targeted tests: **385 passed**, 0 failed/error/skipped; 23 new DETAIL35 tests. Full repository suite not claimed. Seven existing tool/deprecation warnings.
- Final source syntax/compile checks: PASS.
- Real app browser QA: PASS, 1440 / 1280 px; consecutive table edits and input-only JSON roundtrip verified.
- Production Full composite Tn / V–T: WITHHELD.
