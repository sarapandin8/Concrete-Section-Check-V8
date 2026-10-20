# SLAB.SHEAR64 — AASHTO LRFD 2020

ต่อจาก ZIP ที่ตรวจแล้วของ SLAB.AASHTO63 ใช้ AASHTO LRFD Bridge Design Specifications, Ninth Edition (2020), Section 5 ที่ผู้ใช้ให้ เป็นแหล่งหลัก ขอบเขตใหม่คือ Punching shear สำหรับพื้นที่ลงแรงสี่เหลี่ยม และการอ่านผล Interface shear เดิมจาก Flexure

## วิธีใช้

1. เปิด Project JSON เดิม และนำเข้า Excel ทั้ง 4 ชุดเดิมใน Loads → Slab Shell Results ไม่ต้อง export load-combination definitions หรือ moving-load settings เพิ่ม
2. ไป Analysis → Slab Reinforcement กด **Calculate Slab Reinforcement** ครั้งเดียว
3. เลือก **One-way shear**, **Punching shear** หรือ **Reinforcement** จะมีแผนภาพหลักเพียงหนึ่งรูปต่อกลุ่ม/ตัวกรอง รายการวิจัยยังพับเก็บอยู่
4. ที่ **Punching shear → Punching load / reaction areas** กรอกเฉพาะชื่อ, พิกัดศูนย์กลาง X/Y (m), L ตามยาวสะพานและ B ตามขวาง (mm) ของพื้นที่ที่แรงลงถึงผิวพื้นจริงหลังการกระจายแรง กด **Apply load areas** แล้วกด Calculate
5. เว้น **Vu (kN, optional)** ว่างเพื่อใช้ค่าขอบเขตบนจาก shell อัตโนมัติ กรอกเฉพาะเมื่อมี **แรงเฉือนออกแบบที่ใส่ load factor แล้วและถ่ายผ่านหน้าตัดวิกฤตนั้น** จากการตรวจสมดุลแยกต่างหาก ไม่ใช่น้ำหนักเพลาหรือล้อที่ยังไม่พิจารณาแรงอื่นภายในเส้นรอบรูป
6. เปิด **Interface shear · linked from Flexure** เพื่อดูผลราย girder ถ้ายังไม่ได้รันหรือข้อมูลเปลี่ยน ให้กด **Open Final Composite Flexure** แล้ว **Calculate Flexure** ผล Interface ที่ตรงกับข้อมูลปัจจุบันจะปรากฏเมื่อกลับมาหน้าพื้น โดยไม่ต้องรันพื้นซ้ำ

ตำแหน่งเหล็กทั้งสี่ชุด ความหนาพื้นและวัสดุอ่านจากข้อมูลเดิม ไม่ต้องกรอกซ้ำ การแก้เฉพาะพื้นที่ลงแรงใช้ผล One-way ที่ยังตรงกับข้อมูลเดิมได้ จึงไม่ต้องคำนวณส่วนใหญ่ซ้ำ ฟอร์มใช้ Apply ก่อนบันทึกเพื่อลด rerun ระหว่างแก้แต่ละช่อง

## วิธี Punching ที่เพิ่ม

- **5.12.8.6.1**: ค้นหาเส้นรอบรูปที่สั้นที่สุดและห่างจากขอบพื้นที่ลงแรงอย่างน้อย 0.5dv ตรวจทางเลือกภายใน 4 ด้านริม และ 4 มุมของพื้นสี่เหลี่ยม ขอบอิสระไม่นับเป็น b0
- **5.12.8.6.3-1**: Vn = min(0.063 + 0.126/βc, 0.126) λ√fc′ b0 dv โดยใช้หน่วยต้นฉบับ ksi/in/kips แล้วแปลงเป็น MPa/mm/kN, βc = ด้านยาว/ด้านสั้นของพื้นที่ลงแรง, λ=1 สำหรับ normal-weight, φ=0.90
- ใช้ dv อย่างอนุรักษ์นิยมจากระดับเหล็กจริงทั้งสองทิศและสองผิว: max[0.9(h−ระยะศูนย์กลางเหล็กที่ลึกที่สุดจากผิว), 0.72h]
- ไม่เพิ่ม Vs จากตะแกรงเหล็กในระนาบพื้นหรือขา U ที่ยังไม่ได้กำหนดเป็นระบบเหล็กเฉือนทะลุตามข้อกำหนด
- คำนวณเฉพาะ **normal-force punching component** ไม่ใช่การรับรองการถ่าย unbalanced moment หรือ full shell interaction

### แรงอัตโนมัติและการอ่านสถานะ

V13/V23 ของ CSI เป็นแรงต่อหน่วยความยาว โปรแกรมใช้ Vx/Vy หลังเปลี่ยนแกนให้ตรงกับทิศเหล็กจริง แต่ไม่ย้ายจุดอ้างอิงแรง พิจารณาเฉพาะองค์ประกอบตั้งฉากกับแต่ละด้านของเส้นรอบรูป และแบ่งด้านตาม FE ที่ตัดผ่าน

สำหรับแต่ละ FE segment ใช้ค่าสัมบูรณ์สูงสุดของ corner ที่มีส่วนในการ interpolate และทุก step ของ OutputCase นั้น คูณด้วยความยาว segment แล้วรวมเป็น **Vu upper bound** ไม่หักล้างเครื่องหมายตรงข้ามให้ได้แรงต่ำ ไม่เฉลี่ยข้ามองค์ประกอบที่อยู่คนละด้านของขอบ FE และไม่สมมติว่าค่าเคลื่อนที่สูงสุดที่ตำแหน่งต่าง ๆ เกิดพร้อมกัน ค่าขอบเขตนี้ใช้เพื่อพิสูจน์อย่างเพียงพอในขอบเขต normal-force เท่านั้น

| สถานการณ์ | สถานะ |
|---|---|
| ไม่มีพื้นที่ลงแรงจริง | NOT CALCULATED ไม่มี D/C |
| ขอบเขตบน/φVn ≤ 1 | PASS (sufficient) สำหรับองค์ประกอบแรงตรง |
| ขอบเขตบน/φVn > 1 | REVIEW ต้องหาแรงผ่าน perimeter จริงก่อนสรุปว่าไม่ผ่าน |
| กรอก factored design Vu ที่ทราบแล้ว | PASS/FAIL จาก Vu/φVn โดยตรง ในขอบเขต force component |
| ต้องใช้ corner ที่ละเว้นเดิม, ข้อมูล corner/step ขาดหรือไม่ finite | REVIEW ไม่มี Vu/D/C อัตโนมัติ |
| พื้นลาด/พับ, ช่องเปิด/รูปไม่สี่เหลี่ยม, ความหนาเปลี่ยนใกล้หรือบน critical surface, พื้นที่ลงแรงซ้อน, เส้นวิกฤตตัด footprint รองรับต่อเนื่อง | REVIEW ต้องวิเคราะห์หน้าตัด/เส้นทางแรงเฉพาะ |

ตัวเลข D/C ของ demand แบบ bound เป็น **ขอบเขตบน** ไม่ใช่ค่าตรวจจากแรงสมดุลจริง สีเหลืองใช้กับ REVIEW แม้ bound เกิน 1 ตัวอย่าง DEMO ในชุดผลมีทั้ง sufficient PASS, excluded-source REVIEW และ direct-force FAIL เพื่อทดสอบการแสดงผล **พื้นที่และแรง DEMO ไม่ใช่ข้อมูลลงแรงจริงของโครงการ และไม่ได้บันทึกเป็นค่า default**

## Interface shear ที่เชื่อม

อ่านผลเดิมจาก Analysis → ULS Strength → Flexure → Final — Composite → Interface shear โดยใช้ hash ที่ solver เดิมใช้ ตรวจ version, เจ้าของ girder, load rows, geometry, materials, connector/anchorage settings และ minimum reinforcement ด้วย ไม่ใช้เพียง cached headline สีเขียว

ตารางแสดง girder ที่นำเข้าจริงเท่านั้น ผลของ girder หนึ่งไม่ถูกขยายเป็นการตรวจครบทุก girder ในสะพาน ถ้าแก้ active load table แต่ยังไม่ได้เก็บกลับ bank จะถือข้อมูลที่แก้ล่าสุดและให้ผลเก่าเป็น STALE การเปิดหน้าพื้นหรือกดตัวกรองไม่รัน Flexure/Interface อัตโนมัติ

กำลัง Interface เดิมอ้างอิง **5.7.4** สำหรับ longitudinal flexural interface transfer และเหล็ก crossing ที่มี development/anchorage ไม่ใช่การยืนยัน joint opening/roll หรือ joint ทั้งหกองค์ประกอบ และไม่ใช่การนำกำลังเหล็ก U ไปบวกใน punching

## ผลโครงการเดิมและรายการที่ยังต้องทำ

นำเข้า native Top Slab 146,432 records เหลือ 113,232 records หลัง geometry/end exclusions 26,240 และ fixed one-pass peak exclusions 6,960 ผล One-way, reinforcement, source actions ทั้ง 8, row identity และ masks ต้องตรงกับ AASHTO63

| การตรวจ | Max known D/C |
|---|---:|
| One-way transverse shear | 1.490332 |
| One-way longitudinal shear | 3.001741 |
| Transverse flexural shear tie | 1.235121 |
| Longitudinal flexural shear tie | 2.077051 |
| Direct N–M transverse | 0.441277 |
| Direct N–M longitudinal | 0.366523 |

ไฟล์ JSON เดิมไม่มีตำแหน่ง/ขนาดพื้นที่ลงแรง Punching จึงยัง **NOT CALCULATED** และ JSON ที่โหลดใหม่ไม่มีผล Interface runtime ที่เป็นปัจจุบัน ให้คำนวณที่ Flexure ก่อน ค่าตัวเลขที่ไม่ผ่านเดิมไม่ได้ถูกทำให้ผ่านด้วยการเปลี่ยนหน้าจอหรือสูตร Punching

การละเว้นแนว girder/diaphragm, เขตปลายถึง bearing และ isolated peaks เป็นข้อตกลงการ review ของโครงการ ไม่ใช่สิทธิยกเว้นการออกแบบ local load/support region ตาม AASHTO การคง longitudinal shear และ shear tie ไว้ช่วยระบุรายการที่ยังไม่ปิด รวมถึง missing support-face cuts, actual anchorage, Nxy/Mxy/biaxial shear, unbalanced moment/local railway load paths, fatigue และ SLS ตามกรณีที่เกี่ยวข้อง **Overall deck acceptance = REVIEW REQUIRED**

## ขอบเขตการทดสอบและการส่งต่อ

ดู SLAB_SHEAR64_VERIFICATION.json สำหรับจำนวน focused tests, full-input AppTest และตัวเลขเวลาที่วัดจริง การตรวจภาพเป็น Plotly PNG ที่ export แล้วร่วมกับ Streamlit AppTest ไม่ใช่การตรวจหน้าจอ browser จริงครบทุกขนาด

สมการ One-way/N–M/Interface เดิมไม่เปลี่ยน ผลคำนวณยังเป็น runtime-only; Project JSON บันทึกเฉพาะ input พื้นที่ลงแรงเพิ่มใน project metadata และต้องนำเข้า Excel/รันใหม่หลังโหลด Project ใหม่ ไม่มี result-cache persistence เพิ่ม

## แหล่งอ้างอิง

- AASHTO LRFD Bridge Design Specifications, Ninth Edition (2020), Section 5 จากไฟล์ที่ผู้ใช้ให้: 5.12.8.6.1–3 (printed pp. 5-251–5-252), 5.5.4.2 (φ), 5.7.3 และ 5.7.4
- FHWA, Comprehensive Design Example, Two-Way (Punching) Shear: https://www.fhwa.dot.gov/bridge/lrfd/pscus72.cfm (ตัวอย่างสมดุลแรง/สูตร ไม่ใช้เลขข้อเก่าแทนฉบับ 2020)
- CSI shell force conventions: https://docs.csiamerica.com/help-files/csibridge/Output_Conventions/Shell_Element_Internal_Forces_Stresses_Output_Convention.htm
