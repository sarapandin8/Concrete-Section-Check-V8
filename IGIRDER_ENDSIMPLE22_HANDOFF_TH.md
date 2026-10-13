# IGIRDER.ENDSIMPLE22 — กรอกหน้าตัดหัว–ท้ายให้ง่ายขึ้น

เริ่มจาก `concrete-section-pro_IGIRDER-IMPORTSIMPLE21.zip` ที่ตรวจ CRC และ SHA-256 แล้ว

Baseline SHA-256: `ce800cf017bd847b8e0461cea1cb109aeca5789aa7f848e5b0bb8c573ef38a36`

## วิธีใช้งานปกติ

1. เปิด Section และติ๊ก **Enable solid precast end sections**
2. ถ้าหัว–ท้ายเหมือนกัน ใช้ **Same dimensions at both ends** ซึ่งแอปเลือกให้เมื่อค่าทั้งสองด้านเท่ากัน
3. กรอกเพียงสามช่อง

| ช่อง | ความหมาย | ตัวอย่าง |
|---|---|---|
| Solid length at each end (m) | ความยาวช่วงสี่เหลี่ยมเต็มของแต่ละด้าน | 1.500 m |
| Transition length at each end (m) | ช่วงเปลี่ยนจากสี่เหลี่ยมเป็น I เพิ่มจากช่วงตัน | 0.250 m |
| Solid-end width (mm) | ความกว้างสี่เหลี่ยมจริงตามแบบ | 600 mm |

ความสูงใช้ค่าของคานสำเร็จรูปเดิม ไม่รวม deck slab ช่องขวาแสดงหน้าตัดจริงตามตำแหน่งที่เลือก
หากขนาดสองด้านต่างกัน ให้เอาติ๊ก **Same dimensions at both ends** ออก แล้วกรอกแยกซ้าย–ขวา

## พิกัดและรายละเอียดเพิ่มเติม

- ค่าเริ่มต้นใช้ปลายคานที่ x = 0 และ x = L ตามช่วงคานใน Loads โดยแสดงพิกัดที่ใช้อยู่บนหน้าจอ
- **Use full Loads span for girder ends** ใช้ได้เมื่อพิกัดนี้ตรงกับปลายคานสำเร็จรูปจริง หากปลายคานอยู่คนละตำแหน่ง ให้เปิด **More end-section options** แล้วเอาติ๊กออกเพื่อกรอกพิกัดจริง
- โหมดอัตโนมัติตามความยาวช่วงคานปัจจุบัน แม้เพิ่งเปลี่ยน Setup หรือโหลด JSON แล้วยังไม่ได้เปิด Section
- พิกัดเฉพาะและขนาดไม่สมมาตรจากไฟล์เก่ายังคงเดิม ค่าพิกัดเก่าที่ผิดไม่ถูกเปลี่ยนเงียบ ๆ แอปแสดงค่าที่ผิดพร้อมปุ่ม **Use Loads span for girder ends** ให้แก้โดยเลือกเอง
- มุมบากอยู่ใน **More end-section options** ตารางช่วงหน้าตัดอยู่ใน **Section ranges along girder**

## การคำนวณและการยอมรับผล

ช่องตรวจสอบรวมอยู่ใน **Engineering review** ไม่ต้องติ๊กเพื่อให้คำนวณค่ากำลังหน้าตัดได้
ช่องเหล่านี้บันทึกการตรวจที่ทำจริง แอปไม่ติ๊กยืนยันให้อัตโนมัติ เมื่อรายการที่เกี่ยวข้องยังไม่ครบ ผลที่ผ่านเชิงตัวเลขยังคง **REVIEW** และผลที่ไม่ผ่านยังคง **FAIL**

การตรวจ force reference ที่ centroid, เหล็กปลอกและเหล็กรอบหน้าตัดจริง, bearing/anchorage และ D-region เป็นคนละประเด็นกับการกรอกขนาดหน้าตัด
แอปแสดงข้อจำกัดนี้ไว้บนหน้าจอ โดย bearing/anchorage และการตรวจบริเวณปลายคานโดยละเอียดอยู่นอกการคำนวณกำลังหน้าตัดนี้

เมื่อแก้ขนาดหรือช่วงคาน ต้องกด Calculate ULS ใหม่ ระบบใช้ช่วงคานในลายเซ็นข้อมูลของผล ULS ที่เปิดใช้หน้าตัดหัว–ท้าย เพื่อให้ผลเก่ากลายเป็น STALE ก่อนนำมาแสดง

## ขอบเขตการแก้ไข

- Production: `ui/igird_end_sections.py`, `analysis/igird_end_sections.py` และเงื่อนไขลายเซ็นผล ULS ใน `ui/analysis_page.py`
- สมการกำลัง Flexure/Shear/Torsion/V+T เดิมคงไว้ หน้าตัดที่มีขนาดและพิกัดเท่ากันให้ค่ากำลังเดิม
- การนำเข้าแบบ IMPORTSIMPLE21 และการป้องกันใช้แรง Envelope ใน V+T คงไว้ ค่าแรงหกองค์ประกอบและ source metadata ไม่ถูกเปลี่ยนเมื่อกรอกหน้าตัด
- คำประกาศ CSI Correspondence เป็นการระบุแหล่งแรงของวิศวกร ไม่ใช่การพิสูจน์การตั้งค่า export ของ CSiBridge โดยอัตโนมัติ
- SLS และ FE stiffness/self-weight ยังใช้แบบจำลองหน้าตัดสม่ำเสมอเดิม ไม่ได้ปรับให้แปรตามหัว–ท้ายใน milestone นี้
- ไม่เพิ่มการบันทึก solver cache ไม่รัน solver จาก Summary/Report และไม่ได้รัน CSiBridge ใหม่หรือ deploy แอป

## Verification

ชุดทดสอบเฉพาะขอบเขตและ regression 10 โมดูล: **162 passed** บน Streamlit จริง รวมหน้าตัดเดิม การนำเข้าและ source gates, การเปลี่ยนโหมดร่วม/แยก, พิกัดเฉพาะ, JSON roundtrip, การตามช่วงคาน และค่ากำลังเดิม
มี pytest warning เรื่องการ preload anyio เพื่อใช้ Streamlit AppTest ไม่มี skipped tests ในการรันนี้

ตรวจ browser จริงที่ 1440 และ 1100 px: ช่องตัวเลขหลักที่มองเห็นสามช่อง ส่วนพิกัดและการตรวจสอบยุบไว้ เปิดแก้พิกัดเองได้ ไม่มี JavaScript errors
ภาพหน้าจอใช้ตรวจภายใน ไม่รวมภาพที่สร้างใน milestone นี้ในไฟล์ส่งมอบ

ผลทดสอบผ่านแอปจริงและรายละเอียดรายคานอยู่ใน `qa/evidence/igird_endsimple22/app_checks.json`
เส้นทางใช้งานจริงผ่าน: นำเข้า CSI Correspondence ที่ประกาศใน QA, กรอกหน้าตัดแบบง่าย, คำนวณ V+T สองคานรวม 640 แถว, เก็บแรงและ source notes เดิม, แสดง Summary/Report โดยไม่คำนวณซ้ำ และแสดง STALE หลังแก้ขนาด
ได้ D/C เป็นตัวเลข 608 แถว และ 32 แถวที่ x = 0 / 20 m ยังคง DATA REQUIRED โดย solver ระบุว่า transverse geometry, spacing, material หรือ effective depth ไม่ครบในโมเดลทดสอบ ไม่ได้เปลี่ยนให้เป็น PASS เพื่อให้ UI ดูพร้อม
ข้อมูล reinforcement/review ที่ใช้ใน QA เป็นข้อมูลทดสอบ ไม่ใช่การอนุมัติการออกแบบสะพานจริง และการทดสอบนี้ไม่ใช่ชุดทดสอบทั้งหมดของ repository

## Repo summary

```text
Simplify solid girder ends to three shared dimensions, preserve custom ends, and invalidate ULS results when the Loads span changes.
```
