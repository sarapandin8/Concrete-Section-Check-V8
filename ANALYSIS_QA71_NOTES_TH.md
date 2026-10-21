# ANALYSIS.QA71 — ตรวจทั้งสี่ Analysis subpages

ต่อจาก SLS.DEFLECT70 ที่ยอมรับแล้ว ตรวจโค้ดและทดสอบโปรแกรมกับ Project JSON32, ไฟล์ SLS deflection สอง girder และ shell exports เดิมทั้งสี่ชุด ภาพที่ให้มาแสดงรายการเมนู จึงตรวจเส้นทางการใช้งานจริงเพิ่มเติม ไม่ได้สรุปความถูกต้องของสมการจากภาพเพียงอย่างเดียว

## ข้อบกพร่องที่ยืนยันและแก้แล้ว

| ข้อ | เหตุการณ์ในรุ่นเดิม | ผลกระทบ | การแก้ในรุ่นนี้ |
|---|---|---|---|
| 1 | Upload Service envelope → Calculate → Summary/Report → กลับ Analysis | Streamlit ล้าง uploader ที่ถูกซ่อน; แอปเข้าใจว่าเป็นการกด X และลบข้อมูลนำเข้า ทำให้ผล Service กลายเป็น stale; stage/girder ที่เลือกถูกรีเซ็ต | ใช้ callback แยกการกด X จริงออกจากการซ่อน widget, เก็บ normalized input ไว้ และจำ stage/girder ระหว่างหน้า; มี Clear Service import สำหรับข้อมูลที่ยังอยู่แต่ไม่มี upload widget |
| 2 | เปิด Analysis โดยยังไม่ได้ Calculate หรือมีผลเพียงบางโมดูล | สถานะรวมขึ้น Current จากการเข้าหน้า และบางการ์ดยืมสถานะของหน้าก่อน | อ่านสถานะจากผลและ fingerprint ของแต่ละหน้า แสดงจำนวนหน้าที่ current จากทั้งหมด 4 หน้า พร้อมอัปเดตการ์ดและ sidebar หลัง Calculate ใน rerun เดียวกัน |
| 3 | คำนวณ ULS แล้วเปลี่ยนหน้าตัด | Analysis ปฏิเสธผลเก่า แต่ Summary ตรวจ current-input hash ไม่ครบทั้งหก checks จึงอาจยังแสดงค่าเก่า | ให้ Summary/Report ใช้ version และ input hash เดียวกับ Analysis สำหรับ Construction flexure, Final Composite flexure, Interface shear, Shear, Torsion และ V–T; ผลที่ไม่มี signature หรือเป็น legacy generic Flexure ไม่ถูกใช้ |

ข้อ 3 ยืนยันด้วย signed metadata fixture ใน disposable state: เพิ่ม Tslab 10 มม. แล้วรุ่นเดิมยังเก็บ 5 จาก 6 entries ใน Summary ขณะที่รุ่นนี้ปฏิเสธครบ 6 รายการ การทดสอบนี้ไม่ได้รันกำลังหรือสร้างผล PASS ของโครงการ และไม่แก้ JSON ต้นฉบับ

## ผลตรวจแต่ละหน้า

| หน้า | การตรวจใน milestone นี้ | ขอบเขตที่ยังต้องอ่านแยกจากสถานะ Current |
|---|---|---|
| ULS Strength | ตรวจ signatures ทั้งหก checks, result versions, legacy exclusion, Summary/Report และชุดทดสอบ girder strength เดิม | การมีผล current ไม่เท่ากับผ่านกำลังหรือรับรอง full composite research model |
| SLS / Stress & Cracking | Calculate ครั้งเดียวเรียก stage engine 4 ครั้ง; ผ่าน Summary/Report แล้วกลับมา input fingerprint และผลยัง current โดยไม่เรียก engine เพิ่ม | ใช้ขอบเขตและ stress limits ของ stage ที่แสดงในโมดูลเดิม |
| SLS Deflection / Camber | Upload จริงใน browser, สลับทั้งสี่ Analysis หน้า, เปลี่ยน workspace, จำ Service/girder, ล้างด้วย Clear และ X จริง; ทวนข้อมูล source และเส้นกราฟ | Transfer/Construction เป็น elastic single-girder preview; Service ใช้ CSI WebTop Vert envelope ของ girder ที่เลือก; project limit และ full SLS coverage เป็นคนละเรื่อง |
| Slab Reinforcement | รัน JSON และสี่ exports เดิมโดยไม่เปลี่ยนเหล็ก; เปรียบเทียบ 7 CSV กับ accepted 70 แบบ byte-for-byte | REVIEW ของ local support transfer / coupling และ full-deck scope เดิมยังอยู่ ไม่ได้ลบเพื่อให้ผ่าน |

ข้อมูล deflection เดิมให้ Transfer/Construction camber 18.754024 / 13.820283 มม. Service ของ Left Exterior Girder / Interior Girder 2 ให้ |δ|max = 9.227 / 9.160 มม. ที่ x = 10.45714 ม. ทั้งคู่ มีข้อมูล WebTop Vert รวม 96 records ไม่มีการบวก camber, LL หรือ dynamic factor เข้า Service ที่นำเข้า

ผล slab เดิมตรงกับรุ่น 70 ทุกไฟล์ที่เปรียบเทียบ: 109,824 native slab records, 84,864 design records, 24,960 exclusions เดิม ไม่เพิ่มการตัดจุดออก ค่า sectional one-way shear ตามขวาง/ตามยาว = 0.450406 / 0.576383 และ Direct N–M = 0.332482 / 0.254155 สำหรับ JSON เดิมชุดนี้ ไม่ใช่ตัวอย่างที่เปลี่ยนเหล็กทดลอง ผลรวมของ slab ยังเป็น REVIEW REQUIRED ตามขอบเขตเดิม

## การอ่านสถานะใหม่

- **Current 4/4**: ทั้งสี่หน้ามีผลตรงกับ inputs ปัจจุบัน; ไม่ได้แปลว่า design PASS
- **Partial 1/4**: มีผล current ครบหนึ่งหน้า หน้าอื่นยังไม่ครบหรือ stale
- **Stale 0/4**: มีผลเก่าที่ไม่ตรงกับ inputs ปัจจุบัน
- **Not calculated 0/4**: ยังไม่มีผลปัจจุบันและไม่มีผลเก่าให้ทบทวน
- Deflection ที่คำนวณเฉพาะ Transfer/Construction แสดง 2/3 stages ในรายละเอียด; ไม่เติม Service ที่ไม่มีข้อมูล

JSON เก่าอาจมี legacy caches และ global Current flag อยู่ การเปิดไฟล์ดังกล่าวไม่ทำให้ผลเหล่านั้นถูกนับเป็น current โดยอัตโนมัติ View state ไม่ใช่ engineering input และไม่ทำให้ผล stale

## การตรวจซ้ำ

ใช้ Python environment ที่มี dependencies ของแอป และ Playwright/Chromium สำหรับ browser QA:

```bash
python qa/analysis71_regression.py --output /tmp/analysis71-tests
python qa/analysis71_navigation_verify.py --project PROJECT.json --workbook 'SLS deflection.xlsx' --output /tmp/analysis71-browser --expect-retained
python qa/analysis71_stale_cache_verify.py --project PROJECT.json --output /tmp/analysis71-stale.json --expect-rejected
python qa/analysis71_stress_handoff.py --project PROJECT.json --output /tmp/analysis71-stress.json
python qa/sls_deflect70_real_inputs.py --project PROJECT.json --workbook 'SLS deflection.xlsx' --output /tmp/analysis71-deflection
```

หลักฐานอยู่ที่ `qa/evidence/analysis71/` และ `ANALYSIS_QA71_VERIFICATION.json` ผลทดสอบเป็นการตรวจ software regression และ source handling ตามข้อมูลที่ระบุ ไม่ใช่การรับรองงานออกแบบครบระบบ

ไม่เปลี่ยนสมการกำลังหรือ serviceability, แกน/จุดอ้างอิงแรง CSI, agreed slab masks หรือกติกา project JSON ของรุ่น 70 และไม่เพิ่ม result persistence
