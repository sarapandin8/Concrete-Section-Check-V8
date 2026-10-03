# Concrete Section Pro — I-Girder 20 m: Debonding QA และ Flexure runtime

Milestones: **IGIRDER.DBQA1** (AASHTO 9th detailing screen) และ **IGIRDER.PERF3** (Flexure performance).
Base: `concrete-section-pro_IGIRDER-ULS7-concurrent-vt-longitudinal.zip`.
วันที่ 2026-10-03.

## สาเหตุ Error ในรุ่นเดิม

ไฟล์ `I_Girder_20m.json` มี L = 20 m, active strands 34 เส้น, debonded 15 เส้น.
Row 1 มี debond ข้างละ 5 m. QA เดิมใช้ L/5 = 4 m เป็น ERROR และแสดงจำนวน layout errors = 0 ซึ่งนับคนละชุดตรวจ ทำให้ข้อความขัดกัน.
ภาพ `prestress_before.png` ทำซ้ำอาการนี้จาก production renderer รุ่น ULS7 กับ JSON จริง.

AASHTO LRFD 9th Edition Section 5 ที่แนบมา ข้อ 5.9.4.3.3(A-I), printed pages 5-144–145 เป็นแหล่งอ้างอิงของ screen ใหม่.
ข้อ G แนะนำ min(0.20L, 0.5L − ld); ระยะ 5 m จึงต้อง REVIEW. ต้องตรวจ ld ที่ยืนยันแล้วเพื่อปิดเงื่อนไขที่สอง.
ข้อ A ใช้ 45% ต่อแถว เว้นแต่ Owner อนุมัติ. ค่า 25% ในข้อ I เป็น trigger ให้ลวดในแนว web fully bonded ไม่ใช่ขีดจำกัดรวมสำหรับปฏิเสธทุก layout.

## ผลจากโมเดลที่ส่งมา

| ตรวจ | ข้อมูลจริง | ผล screen / สิ่งที่ต้องทำ |
|---|---|---|
| Per-row ratio, A | Row 1–3: 4/9 = 44.4%; Row 4: 3/7 = 42.9% | OK สำหรับเกณฑ์ 45%; ไม่ใช้ 40% generic เดิม |
| Total ratio, I | 15/34 = 44.1% | Trigger web-projection bonding ทำงาน |
| Web projection, I | web 200 mm; Row 1–3 #4/#6 ที่ x = −55/+55 mm; Row 4 #4 ที่ x = 0 mm ถูก debond | FAIL: ลวดเหล่านี้ต้อง fully bonded ภายใต้ trigger ที่ใช้ |
| Outer-most flange strands, I | Row 4 #1/#7 เป็นลวดริมสุดใน full-width bottom flange | FAIL: ต้อง fully bonded |
| Alternating positions, E | เลือกตำแหน่ง x เดียวกันในแถวข้างเคียงแนวดิ่ง | FAIL: จัด bonded/debonded ให้สลับ และตรวจแบบ |
| Termination count, B | ทุกตำแหน่ง 3 หรือ 4 เส้น; total debonded > 10 | OK สำหรับ cap 6 เส้น/section |
| Termination spacing, C | ระยะน้อยสุด 1 m; db = 12.7 mm; 60db = 762 mm | OK |
| Length recommendation, G | Row 1: 5 m > 0.20L = 4 m | REVIEW พร้อมตรวจ bound 0.5L − ld |
| Development / strength, F/I | ยังไม่มี verified strand ld และผล service-tension applicability ใน screen นี้ | REVIEW; ปิดกับ strength/development/SLS และแบบจริง |

**ลด Row 1 จาก 5 เป็น 4 m อย่างเดียวไม่พอ:** จะรวมกับ Row 2 เป็น 8 เส้น terminate ที่ x = 4 และ 16 m เกิน 6 เส้น/section และยังมี FAIL เรื่องตำแหน่งลวด.
การแก้แบบต้องประเมิน effective prestress, transfer stress, SLS และ ULS ใหม่. งานนี้รักษา JSON/การเลือกลวดเดิมไว้เพื่อให้ข้อผิดพลาดตรวจสอบได้.

## Flexure performance

| รายการ | รุ่น ULS7 เดิม | PERF3 |
|---|---:|---:|
| Final Composite, 21 physical stations | 164.57 s | 50.14 s |
| PMM sweeps | 21 | 5 |
| Neutral-axis resolution | 72 × 120 | 72 × 120 |

เร็วขึ้น **3.28 เท่า**, ลดเวลาคำนวณ **69.5%**, จับเวลา kernel และ station audit บนเครื่องเดียวกัน.
ค่าตัวเลข 11 columns ทุก 21 stations ตรงกันทุกค่า รวม Mn, φMn, D/C, neutral-axis depth และ angle. ข้อสรุปนี้เป็น differential regression กับ baseline ไม่ใช่การรับรองความถูกต้องทางวิศวกรรมโดยอิสระ.
กด Calculate Final Composite Flexure ใน local browser จริงสำเร็จ (~53.5 s ในการตรวจหน้าจอ); ค่านี้ไม่ใช่การรับประกัน latency ของระบบที่ deploy.

## สิ่งที่เปลี่ยน

1. Scoped AASHTO 9th I-Girder QA อ่านตำแหน่งลวดจริง แยก ERROR (invalid input), FAIL (detected detailing violation), REVIEW (recommendation/unverified requirement), พร้อม clause และ strand number.
2. แสดง layout errors, rule failures, review counts แยกกัน. Prestress sidebar แยก input readiness จาก debonding detailing.
3. Flexure reuse physical PMM clouds ภายใน Calculate ครั้งเดียว แต่ยัง slice/check ตาม Nu และ moment ของแต่ละสถานี. หน้าตัด/วัสดุ/เหล็ก/แรงอัดลวด/จำนวนลวด/bonded state/resolution ที่ต่างกันสร้าง cloud ใหม่.
4. PMM slice ใช้ adjacent axial values ตามลำดับเดิม และสร้าง pandas Series เฉพาะสองแถว bracket; math.hypot, interpolation, duplicates, fallback และ metadata ใช้พฤติกรรมเดิม.

Core PMM equilibrium, prestress constitutive law, capacity-check engine, ULS7 V+T, composite model และ Project IO ตรงกับ baseline แบบ byte-for-byte. เกณฑ์ QA ที่ปรับเป็น code-edition screen แยกจากสมการกำลังเดิม.
Summary/Report ใช้ stored results ตามเดิม. ไม่มีการเพิ่ม result persistence เข้า JSON.

## Validation

- Selected regression: **452 passed**, 0 failures/errors/skips, 46 modules. ไม่ได้อ้างว่า run repository suite ทั้งหมด.
- 80 cases เปรียบเทียบ PMM slice กับ source จาก ULS7 เดิม: DataFrame และ attrs ตรงกันทุกค่า; ครอบคลุม duplicates, exact Pu, brackets, NaN, capped Pu, out-of-range, empty/fallback และ shuffled input.
- Compile app.py และ modified modules: PASS.
- Production app.py startup: PASS; actual production Prestress/Analysis renderer ใน local browser: ไม่มี page error หรือ Streamlit exception.
- Source fixture SHA-256: `c27a27278fef69b5347e7216f5b3c9324f723a9a0ca2d5b52a8956c1fe765799`; bytes เหมือน JSON ที่ผู้ใช้แนบ.
- Full ZIP fresh-extract validation และ SHA/size/entries อยู่ใน companion release manifest.

## Run

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

โหลด project JSON แล้วเปิด Sections → Prestress → Debonding QA.
Flexure: Analysis → ULS → Flexure → Final — Composite → Calculate Final Composite Flexure.
Reproducible actual-model QA view: `python -m streamlit run qa/igird_dbqa_perf_runtime.py`.
`qa/fixtures/I_Girder_20m.json` เป็น original QA input ไม่ใช่แบบที่แก้ผ่านแล้ว.

## Remaining handoff

ปิด detailing/development/service checks ของ layout จริงก่อนยอมรับแบบ.
Composite model เดิมมี Be_strength_verified = false และ interface shear ยังเป็น acceptance gate แยก; section Flexure PASS ไม่ครอบคลุมเงื่อนไขเหล่านี้.
ENV_ULS เป็นชื่อ envelope ที่ยังไม่มีหลักฐาน load-step concurrency ใน JSON; ต้องตรวจแหล่ง FEA ก่อนใช้ผล concurrent V+T เป็นคำตอบสุดท้าย. งานนี้ไม่ได้รวมแรงจากคนละ station/case เพิ่ม.

Repo summary: Correct AASHTO 9th I-Girder debonding QA and accelerate full-span flexure through physical PMM-cloud reuse and equivalent slice lookup.
