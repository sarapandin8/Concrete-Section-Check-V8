> Subsequent Analysis presentation: MODELTN47 uses the U + slab Model Tn as the primary view; I-hoop checks are reference. CSI torque policy and resistance equations below remain unchanged. See `IGIRDER_MODELTN47_HANDOFF_TH.md`.

# IGIRDER-CSITU46 — ใช้ Tu จาก CSiBridge ณ จุดรายงานเดิม

วันที่ 18 ตุลาคม 2026 · พัฒนาจาก IGIRDER-STEEL45-REVIEW

แก้ Torsion และ Shear + Torsion ให้ใช้ **Tu ต้นทางจาก CSiBridge โดยไม่ย้ายไป centroid ของคาน I** พร้อมให้ตาราง Model ใช้ Tu ชุดเดียวกัน จุดรายงานเดิมอาจอยู่ที่ระดับ CG ของ Full Bridge Section และแนว Center of Girder Web ตามค่าตั้งต้น CSI

## วิธีใช้งาน

1. แตก ZIP และเปิดแอปด้วย `streamlit run app.py` ตามวิธีเดิม
2. โหลด Project JSON เดิมได้ ไม่ต้องแก้ Loads หรือกรอกแบบฟอร์มใหม่
3. ไป Analysis แล้วกด Calculate Torsion หรือ Calculate Shear + Torsion ปุ่มเดิม
4. อ่าน `CSI force reference / Equations`: แถว T แสดง `T_used = T_CSI (unchanged)` และมีคำอธิบายภาษาไทยว่าไม่ย้ายไป centroid คาน I
5. ผลก่อน CSITU46 มีลายเซ็นนโยบายต่างกัน จึงไม่ถูกนำมาใช้เป็นผลปัจจุบัน ต้อง Calculate ใหม่

## สิ่งที่เปลี่ยน

- ตัวแปลงสำหรับ Torsion และ V–T คืน Tu ดิบจากแหล่ง CSI แม้แถววิเคราะห์เคยถูกย้ายจุดมาก่อน ป้องกันการแปลงซ้ำ
- ไม่บวก `r2·V3−r3·V2` เข้า Tu ที่ใช้ในสองการตรวจนี้
- โมเดล I + U–พื้นเลือกแถวที่ |Tu ต้นทาง CSI| สูงสุดต่อ girder แทนการเลือกจาก Tu ที่ย้ายไป centroid คาน I การเลือกนี้ยังเป็นตัวอย่างหนึ่งแถวต่อ girder ไม่ใช่การค้นหา D/C สูงสุดครบทั้งช่วง
- ตารางผล กราฟ และ calculation trace ของการตรวจเหล่านี้อ่าน Tu จากผลคำนวณปัจจุบัน การติดตามผลเก็บพิกัดจุดรายงาน CSI และระบุ `T shift applied = false`
- เพิ่มนโยบาย `IGIRDER.CSITU46.reported-torque` ในลายเซ็นผลคำนวณ และเพิ่มเวอร์ชันของโมเดล review เพื่อป้องกันการแสดงผลเก่า
- ไม่เพิ่มปุ่ม Run, checkbox หรือข้อมูลที่ผู้ใช้ต้องกรอก

## ขอบเขตของการแก้ไข

การแก้นี้เป็นนโยบาย **Tu ต้นทาง CSI** ตามคำสั่งผู้ใช้ ไม่ใช่การเปลี่ยนให้แรงหกองค์ประกอบอยู่ที่จุดเดียวกันทั้งหมด:

- P, V2, V3 คงค่าต้นทาง
- M2/M3 ยังคงแปลงตามจุดอ้างอิงของการตรวจดัด การตรวจดัดและ SLS ไม่ถูกเปลี่ยนนโยบาย
- สมการย้ายเวกเตอร์โมเมนต์ทั่วไปยังใช้สำหรับงานสมดุลขององค์ประกอบและการตรวจดัด ไม่ได้ถูกลบหรือแก้เครื่องหมาย
- สมการกำลังและปริมาณเหล็กคงวิธีเดิม ค่า theta, Tn และ D/C อาจเปลี่ยนตามค่า Tu ใหม่ เพราะ General Procedure ขึ้นกับแรงที่กระทำ
- ไม่มีการคูณเพิ่มกำลัง ไม่ลด Tu ด้วย compatibility redistribution ไม่ตั้งแรงบิดเป็นศูนย์ และไม่เปลี่ยนแถว envelope ให้เป็น concurrent โดยอัตโนมัติ
- การใช้ Tu ที่จุดรายงาน CSI ไม่ได้พิสูจน์ว่ากำลังปลอก I หรือโมเดลสองเส้นทางเป็นความต้านทานของหน้าตัดประกอบที่จุดนั้น การตรวจหลักยังมีขอบเขต I-hoop screening และตารางระบบร่วมยังเป็น MODEL REVIEW ผลที่ตัวเลขต่ำกว่า 1 ยังคง REVIEW เมื่อขอบเขตกำลังไม่ครบ
- ผล review ยังแยกจาก production cache / Summary / Report / Project JSON และไม่มี accepted full-composite Tn หรือ V–T เพิ่มขึ้นจากการแก้ครั้งนี้

## ตัวอย่างจาก JSON โครงการเดิม

ต้นทาง: `concrete_section_pro_project_31_COVER38.json`  
SHA256: `0ae85f6de0b753062393a70717105953836a4a7722449edfbdc0e91ba8f99fcb`

ตัวอย่าง U2A ที่ x=18 ม. เทียบกับ STEEL45 รุ่นก่อนหน้า:

| Girder | Tu ที่ใช้เดิม หลังย้ายจุด (kN·m) | Tu ที่ใช้ CSITU46 จาก CSI (kN·m) | V–T D/C เดิม | V–T D/C ใหม่ | สถานะใหม่ |
|---|---:|---:|---:|---:|---|
| BOBJ1 / Interior Girder 2 | 462.7460 | 286.8371 | 2.5263 | 1.4843 | FAIL |
| BOBJ1 / Left Exterior Girder | -395.4074 | -190.3973 | 1.5277 | 0.6816 | REVIEW |

ค่า D/C ในตารางเป็นผลการตรวจที่ยังมีข้อจำกัดของกลไกกำลังเดิม ไม่ใช่ผลยืนยัน full composite และไม่ใช้พิสูจน์ว่าโครงสร้างจริงผ่านหรือไม่ผ่านครบทั้งระบบ

## การตรวจสอบ

- 180 selected tests ผ่าน รวม 12 tests ใหม่ของการใช้ Tu ต้นทาง ไม่ได้รันทั้ง repository
- เว้น 1 test เดิม `test_different_vectors_at_one_case_station_are_not_enveloped` ซึ่งล้มเหลวเหมือนกันใน REFERENCE43: fixture ไม่ผ่าน concurrent-source gate การแก้นี้ไม่ปลด gate เพื่อให้ test ผ่าน
- ตรวจ 640 source rows × 2 readers = 1,280 การแปลง: Tu ที่ใช้ตรงกับ CSI ทุกแถว และไฟล์ต้นทางไม่ถูกแก้
- ตรวจ Calculate Torsion และ V–T จริงสำหรับตัวอย่างสอง girder รวมถึง Model selection, การแยก review cache และลายเซ็นผลคำนวณ
- ชุด SLS import, สมดุลเวกเตอร์ทั่วไป และกราฟเต็มช่วงผ่าน
- `py_compile` ผ่าน app.py และโมดูลที่แก้/เพิ่ม
- Streamlit AppTest ผ่าน: ไม่มี exception, แสดง Tu=286.8371 ตรงต้นทาง, มีคำอธิบายจุดอ้างอิง, ตารางเปรียบเทียบ 6 แถว และไม่มีปุ่มหรือ checkbox เพิ่ม
- ยังไม่ได้ตรวจ screenshot ใน browser จริง เพราะ environment ไม่มี browser binary จึงไม่อ้างว่าผ่าน browser visual QA

หลักฐานอยู่ใน `qa/evidence/igird_csitu46/` รันตรวจซ้ำได้ด้วย:

```bash
python qa/validate_csitu46_project.py --project PATH_TO_PROJECT.json --output csitu46_results
```

## Repo summary

Use native CSI Tu for Torsion, V–T and composite review; preserve bending transport, source data and resistance scope guards; update trace/selection and invalidate legacy torque-policy results. No new user inputs.
