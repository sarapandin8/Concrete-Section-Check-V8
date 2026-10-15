# IGIRDER.CSIREF26 — จุดอ้างอิงแรงจาก CSiBridge

วันที่: 14 ตุลาคม 2026

รุ่นนี้เพิ่มการเชื่อมจุดรายงานแรงของ CSiBridge กับจุดอ้างอิงที่ใช้ตรวจหน้าตัดใน Concrete Section Pro โดยเก็บแรงต้นฉบับไว้ครบและแปลงเฉพาะแถวสำหรับการวิเคราะห์ เป็นขั้นแรกของการเชื่อม Girder resultants กับกำลังหน้าตัด ส่วนกำลัง composite shear–torsion ทั้งระบบยังไม่เสร็จ

## วิธีใช้กับโครงการปัจจุบัน

1. แตกชุดแอป CSIREF26 ติดตั้งตาม `requirements.txt` และเปิดด้วย `streamlit run app.py`
2. เปิด Project JSON `I_Girder_20m_CSIREF26.json` ซึ่งเตรียมจากไฟล์เดิมของผู้ใช้แล้ว
3. ใน Loads → ULS หรือ SLS เปิด `CSI force output reference` เพื่อตรวจจุดรายงาน ค่าโครงการนี้คือ 0.615600 m ใต้ deck top และ local 3 offset = 0 m ที่แนวกึ่งกลาง web ไม่ต้องกรอกซ้ำเมื่อใช้ JSON ที่จัดให้
4. Upload ไฟล์ Loads จาก CSiBridge ผ่านขั้นตอนเดิม แรงตัวเลขในตารางยังเป็นแรงที่โปรแกรมรายงานที่จุด C
5. Calculate ใหม่ใน Analysis ผลและ Calculation trace จะแสดงจุด C, จุด O, ระยะ C−O และสมการที่ใช้แปลงแรง ผลที่คำนวณก่อนเปลี่ยนจุดอ้างอิงต้องคำนวณใหม่

ค่า 0.615600 m ใช้เฉพาะโมเดลต้นทางปัจจุบัน ไม่ใช่ default สำหรับสะพานทุกแบบ หากเปลี่ยนความหนา slab ความสูง/จำนวน/ตำแหน่งคานในโมเดลสะพานจริง ต้องวิเคราะห์ CSiBridge ใหม่และนำเข้า Loads กับข้อมูลจุดอ้างอิงใหม่ การแปลงจุดอ้างอิงไม่คำนวณการกระจายแรงหรือ stiffness ใหม่ให้

หากเปลี่ยนหน้าตัดผู้สมัครในแอปเพื่อทบทวนกำลังภายใต้แรงเดิม ระบบจะคงจุดรายงาน C จากไฟล์ต้นทาง และคำนวณ O ตามหน้าตัดผู้สมัครแต่ละ station โดยถือ deck top เป็น datum ร่วม การทำเช่นนี้ยังไม่ใช่การวิเคราะห์สะพานที่เปลี่ยน stiffness แล้ว

## ค่าจากรูป CSiBridge ที่ผู้ใช้ให้

| รายการ | ค่า |
|---|---:|
| Section Reference Point Y | 1.850000 m |
| Full Bridge Section Ycg | 1.234400 m |
| ความลึกจุด C ใต้ deck top | 0.615600 m |
| ตำแหน่งแนวราบของผล Girder | Center of Girder Web |
| offset local 3 จาก web | 0.000000 m |
| Force kind | GIRDER_COMPOSITE |

ใช้ Ycg ของ full bridge section สำหรับแนวดิ่ง แต่ไม่ได้ใช้ Xcg = 5.5 m เป็นตำแหน่งแนวราบของทุก Girder ตำแหน่งแนวราบผูกกับแนว web ของแต่ละ Girder

ข้อมูลจุดรายงานถูกเก็บใน project metadata และแนบ snapshot ลงใน source Note ของแถว Loads โดยยังเก็บ raw_fields เดิม การนำเข้าไฟล์ใหม่ไม่เขียนทับ snapshot เก่า ปุ่ม `Save CSI reference and apply to current files` เป็นการเปลี่ยนจุดอ้างอิงของไฟล์ปัจจุบันโดยตั้งใจและล้างผลที่เกี่ยวข้อง ไม่มี checkbox ยืนยันเพิ่มเติมในแผงนี้

## การแปลงแรง

ชุดนำเข้าใช้ P, V2, V3, T, M2, M3 ในแกน local ของ CSI ที่รองรับ โดย P บวกคือแรงดึง และเวกเตอร์โมเมนต์เชิงกายภาพตาม convention นี้คือ (T, −M2, M3)

ให้ r = C−O, r1 = 0 และใช้หน่วยแรง kN ระยะ m โมเมนต์ kN-m:

```text
T_O  = T_C  + r2 V3 − r3 V2
M2_O = M2_C − r3 P
M3_O = M3_C − r2 P
P_O = P_C; V2_O = V2_C; V3_O = V3_C
```

นี่คือการถ่ายโมเมนต์ของ resultant เดิม ไม่ใช่การแยกแรงของ slab ออกจาก I-girder ไม่ทำให้กำลังวัสดุเพิ่มขึ้น และไม่ทำให้ Tu ที่จุด O กลายเป็นแรงบิดของ I-girder เพียงชิ้นเดียวโดยอัตโนมัติ Section Cuts ในแกน global ยังไม่รองรับการหมุนแกนอัตโนมัติในรุ่นนี้ และข้อมูลที่ระบุ axes ไม่ตรงจะถูกปฏิเสธ

ULS แปลงชั่วคราวก่อนเข้าสู่ตัวตรวจ ส่วน SLS แปลงไปยัง centroid ของ elastic/transformed stress basis ที่ตัวตรวจเลือกอยู่ ป้าย N ของ SLS ใช้ compression-positive และยังคงการแปลงเครื่องหมายเดิม การคำนวณซ้ำ/เปลี่ยนจุด O ใช้ข้อมูลต้นทางที่เก็บไว้ จึงไม่บวกระยะเยื้องซ้ำ

## ผลตรวจไฟล์จริง

ตรวจ Interior Girder 1 ในไฟล์ DL และ U2A ที่ผู้ใช้ส่ง และสร้าง JSON สำเนาซึ่งตั้งจุดอ้างอิงแล้ว โดยไฟล์ต้นทางทั้งสามไฟล์มี SHA-256 เดิมหลังตรวจ

| ชุดข้อมูล | แถว | วิธีแปลง |
|---|---:|---|
| DL / DEAD | 46 | EXACT: ผู้ใช้ยืนยันว่าเป็น static DL |
| U2A native Max/Min | 92 | INTERVAL BOUND: ขอบเขตองค์ประกอบที่ไม่ทราบ correlation |
| ULS member bank ใน Project JSON | 640 | เพิ่ม source snapshot โดยคงตัวเลข Loads |
| Active ULS table ใน Project JSON | 320 | เพิ่ม source snapshot โดยคงตัวเลข Loads |

ตัวอย่าง DL / Interior Girder 1 / x = 10.45714 m / occurrence 1:

| ค่า | จุด C เดิม | จุด O ของ composite section |
|---|---:|---:|
| P (kN) | 274.289 | 274.289 |
| T (kN-m) | −0.651500 | −0.798334 |
| M2 (kN-m) | 1.448300 | 1.448300 |
| M3 (kN-m) | 1336.447600 | 1311.400929 |

สำหรับหน้าตัด I + slab 1.20×0.35 m ของตัวอย่างนี้ r2 = 0.091314894 m และ r3 = 0 ตัวอ่าน flexure จริงได้รับ M3 ที่แปลงแล้วเพียงครั้งเดียว การแปลง DL กลับไปจุดเดิมมีความคลาดเคลื่อนสูงสุด 1.78×10⁻¹⁵ kN-m ผล flexure ตัวอย่างยังเป็น REVIEW ตามขอบเขตการตรวจเดิม

ค่าที่จุด O ในตารางตัวอย่างใช้ geometric composite centroid สำหรับ flexure ตัวอย่าง ไม่ใช่ centroid ของทุก Girder ทุก station หรือทุก SLS stress basis

## Envelope และ concurrence

Max/Min แยกองค์ประกอบไม่ได้พิสูจน์ว่าแรงทั้งหกเกิดพร้อมกัน ระบบจับคู่ Max/Min ตาม source file, Girder, case, physical cut, occurrence และ station แล้วถ่ายขอบเขตเชิงเส้น หากไม่มีคู่ที่ชัดเจนจะ BLOCKED และไม่ใช้โมเมนต์ที่เดาไว้

INTERVAL BOUND เป็น screening bound ไม่ได้สร้าง concurrent state และผลที่จะ PASS ถูกปรับเป็น REVIEW การใช้แรง N/M จาก extrema คนละสถานะไม่ได้ถูกยืนยันว่าเป็นชุดแรงจริง หาก source เดิมมีคำประกาศ correspondence ที่ชัดเจน ระบบคงสัญญาข้อมูลนั้นและแสดง `Declared correspondence` ซึ่งยังไม่ใช่การพิสูจน์ concurrency จากชื่อ Max/Min

## ขอบเขตกำลังที่ยังค้าง

- Flexure ที่พัฒนามาในแอปยังเป็น primary M3 route; full P–M2–M3 resistance ยังไม่เพิ่มใน milestone นี้
- V2 sectional shear ใช้เส้นทางเดิม ส่วน V3/deck transverse shear และผลร่วมครบระบบยังต้องตรวจแยก
- Torsion และ V+T เดิมใช้ I-girder hoop geometry จึงไม่รับรองกำลัง composite girder ทั้งระบบเมื่อ demand เป็น GIRDER_COMPOSITE
- V+T partial route มี M2/M3 ที่ composite centroid และ T ที่ I-section centroid แยกกัน พร้อม trace ของทั้งสองจุด เป็นการตรวจบางส่วน ไม่ใช่ equivalent single-origin composite mechanism หรือการหา shear center
- การถ่ายโมเมนต์ไม่ได้เพิ่ม Ao, เหล็กปลอก, เหล็ก deck, กำลัง interface หรือกำลังคอนกรีตที่ให้เครดิต
- Slab transverse reinforcement/anchorage, interface transfer และ bearing/diaphragm D-region ยังต้องมีข้อมูลและกลไกที่ยืนยันได้ก่อนสรุป full composite V–T acceptance
- Source Section Points reader อ่านรูปหลาย polygon และจำนวนคานที่เปลี่ยนได้ แต่ยังไม่ได้สร้าง effective slab width หรือเหล็กของแต่ละ Girder อัตโนมัติ รูปแบบรายละเอียดคานยังเป็นโครงสร้างข้อมูลเดิมของแอป
- หน้าตัด source ต่างวัสดุหรือไม่ระบุวัสดุ ต้องใช้ Ycg ที่ CSiBridge รายงาน ไม่สมมติ area centroid ให้เอง รองรับหน่วยพิกัดที่ประกาศ m/mm/cm/ft/in

## การทดสอบและข้อจำกัดการตรวจ

ตรวจ compile `app.py` และโมดูลที่เปลี่ยนทั้งหมดผ่าน ชุด targeted/regression ล่าสุดผ่าน 77 รายการ รวม 19 รายการใหม่ของ CSIREF26 ครอบคลุมเครื่องหมาย cross product, การแปลงกลับ, corner bounds, source snapshots, JSON roundtrip, หน่วยพิกัด, แกนที่ไม่รองรับ, centroid เมื่อ slab/จำนวนคานเปลี่ยน, flexure consumer, V+T origin trace, charts และ SLS import

ทดสอบแผง reference กับ Project JSON จริงและ DL numerical trace ด้วย Streamlit AppTest ผ่านเพิ่มเติม แต่ตรวจภาพหน้าจอในเบราว์เซอร์ไม่สำเร็จ เพราะเบราว์เซอร์เชื่อมต่อ local app ไม่ได้ จึงไม่อ้างว่า browser visual verification ผ่าน

Regression วงกว้างรอบก่อนตรวจ 771 รายการ: ผ่าน 764 และไม่ผ่าน 7 รายการ โดยทั้ง 7 ข้อให้ผลไม่ผ่านเหมือนกันใน baseline เดิม ส่วนใหญ่เป็นข้อคาดหวังเก่าก่อน concurrence gate หรือ version string ไม่ได้แก้ให้ข้าม source gate เพื่อให้เป็นสีเขียว รุ่นนี้จึงไม่ได้อ้าง full-suite PASS

รายชื่อข้อเดิมที่ไม่ผ่าน:

```text
test_igird_axial_convention.py::test_every_uls_consumer_matches_independently_preconverted_force[200]
test_igird_axial_convention.py::test_every_uls_consumer_matches_independently_preconverted_force[-200]
test_igird_uls5_shear_general_procedure.py::test_igird_combined_vt_with_missing_composite_fps_source_remains_review
test_igird_uls6_torsion_general_procedure.py::test_igird_combined_guard_now_points_to_longitudinal_equation_not_fixed_theta
test_igird_uls6_torsion_general_procedure.py::test_vtqa1_versions_invalidate_all_vt_development_sources
test_igird_uls7_concurrent_vt.py::test_different_vectors_at_one_case_station_are_not_enveloped
test_igird_vtqa1.py::test_reference_m2_v3_do_not_change_primary_numeric_results[Shear + Torsion-_beam_uls_combined_vt_check_dataframe]
```

## สำหรับผู้พัฒนารอบถัดไป

โค้ดหลักอยู่ที่ `io/csi_force_reference.py`, `ui/csi_force_reference.py`, `ui/csi_reference_analysis.py` ส่วนตัวอ่านเดิมเชื่อมผ่าน decorators และ station wrapper มี audit ของไฟล์จริงใน `qa/evidence/igird_csiref26/` และสคริปต์ `qa/igird_csiref26_actual_review.py`

เริ่มจาก working tree ที่สืบต่อ FLEXREVIEW25 ไม่มีการนำกลับไปเริ่มจาก SLSIMPORT23 ZIP เก่าและไม่มีการเพิ่ม result-cache persistence การเปลี่ยนนี้เพิ่ม demand-transport equations และเปลี่ยนจุดที่ตัวอ่านแรงใช้งาน แต่ไม่ได้เพิ่ม nominal resistance equations หรือ composite V–T mechanism

Copyable commit summary:

```text
IGIRDER.CSIREF26: Bind immutable CSI force-reference snapshots to native ULS/SLS imports; transport demand moments to each resistance origin without changing raw Loads; trace exact/interval mappings and retain REVIEW for incomplete full-Girder resistance mechanisms.
```
