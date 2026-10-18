# IGIRDER-MODELTN47 — ใช้ Model Tn รวม U + เหล็กพื้นใน Analysis

วันที่ 18 ตุลาคม 2026 · พัฒนาจาก ZIP IGIRDER-CSITU46 ที่ส่งล่าสุด

หน้า Analysis ของ composite I-girder ใช้ **Model Tn รวม U สองขาและเหล็กยาวพื้น** เป็นค่าหลัก พร้อม Model Vn และ Model nominal V–T D/C จากโมเดลร่วมเดียวกัน ผลปลอก I-girder เดิมย้ายไป **Reference checks — I-girder hoop / code route** เพื่อให้ความหมายของกำลังทั้งสองวิธีชัดเจน

## วิธีใช้

1. แตก ZIP และเปิดด้วย `streamlit run app.py` ตามเดิม
2. โหลด JSON โครงการเดิม
3. ไป Analysis → ULS แล้วเลือก **Torsion** หรือ **Shear + Torsion**
4. กด Calculate ปุ่มเดิม หากมีหลาย girder ให้ใช้ปุ่ม Calculate … all … girders ปุ่มเดิม
5. อ่านตาราง **Composite resistance — U + slab steel** ก่อน แล้วเปิด Girder ที่ต้องการเพื่อดู Model Tn, Model Vn, nominal V–T D/C และ trace
6. เปิด **Same-model comparison — reinforcement contribution** เพื่อเทียบโมเดลเดียวกันแบบรวม/ไม่รวม U และไม่รวมเหล็กยาวพื้น
7. เปิด Reference checks เมื่อจะอ่านผลปลอก I, กราฟเต็มช่วง และ code-check trace เดิม

ใช้ข้อมูลเหล็ก U, เหล็กพื้น และระยะพัฒนาแรงเดิม ไม่ต้องกรอกซ้ำ ไม่มีปุ่ม Calculate หรือ checkbox ใหม่ ผลเก่าก่อน MODELTN47 ถูกแยกด้วยลายเซ็นเวอร์ชัน ต้อง Calculate ใหม่

## ฐานของผลที่เลือกใช้

- Model Tn และ Model Vn เป็นกำลัง **nominal** ที่ M=N=0 โดยใช้ θ คงที่จากแถวแรงต้นทางที่เลือก
- Model V–T คง M3/N ของแถวจริง แล้วเพิ่ม V2/T ด้วยตัวคูณร่วม ไม่บวก Vn กับ Tn ซึ่งมีหน่วยต่างกัน
- ใช้พื้นที่หนึ่งขาของ U ในสมการ torsion และสองขาจริงในการจัดสรร shear โดยใช้กำลังเหล็กร่วมกันครั้งเดียว
- เหล็กยาวพื้นถูกนับตามตำแหน่งและเงื่อนไขระยะพัฒนาแรงเดิม
- Tu ใช้ค่ารายงาน CSI เดิม ไม่ย้ายไป centroid คาน I ส่วน M2/M3 ยังคงนโยบายอ้างอิงดัดของ CSITU46
- แสดง **MODEL REVIEW** เสมอ พร้อม `WITHIN NOMINAL` หรือ `EXCEEDS NOMINAL` สำหรับ nominal V–T; ไม่สร้าง φ, φTn หรือ PASS สำหรับออกแบบจากโมเดลนี้

## ขอบเขตและสถานะการยอมรับ

การเลือก Model Tn นี้เป็นค่าหลักใน Analysis เป็นการเลือกใช้โมเดลที่มีอยู่ **ไม่ได้ทำให้โมเดลผ่าน structural validation** สมการและข้อจำกัดเดิมไม่ได้ถูกเปลี่ยน:

- fixed-angle fully cracked truss และไม่รวม Vc/cohesion
- เพดานกำลังคอนกรีตร่วมยังอิง web ของ I-girder; ยังไม่เพิ่มเพดานตาม slab ทั้งหมด
- การแบ่งเหล็กยาวคาน I และพื้นตามเส้นทางเป็นสมมติฐานเดิม
- เส้นทาง U–พื้นและ strain/slip compatibility ยังต้องตรวจยืนยัน ความยาว hook เพียงอย่างเดียวไม่พิสูจน์กำลังบิดรวม
- โมเดลเลือก **หนึ่งแถวที่ |Tu ต้นทาง CSI| สูงสุดต่อ girder** จากชุดแถวที่คำนวณ โดยไม่เลือกปลายกายภาพ 0/L จึงเป็นตัวอย่างของ source row ที่เลือก ยังไม่ใช่การค้นหา V–T D/C สูงสุดตลอดสะพาน
- คง concurrent-source declarations เดิม ไม่เปลี่ยน envelope ให้เป็น concurrent อัตโนมัติ
- กำลังร่วม M2/V3 และความต้านทานที่จุดรายงาน CSI เต็มระบบยังไม่ได้ตรวจยืนยัน

Result Summary / Report / QA ยังคงอ่าน code checks เดิม ไม่แทนด้วยค่าทดลอง nominal ผลโมเดลแยกจาก production caches และ Project JSON; Summary และ Report ไม่รัน solver เพิ่ม

## ตัวอย่างตรวจด้วย JSON โครงการ

ไฟล์ `concrete_section_pro_project_31_COVER38.json`  
SHA-256: `0ae85f6de0b753062393a70717105953836a4a7722449edfbdc0e91ba8f99fcb`

ทดสอบ app.py ด้วยสอง source rows เดิม U2A ที่ x=18 ม. โดยลดชุดแถวใน memory เฉพาะ QA ไม่ได้เปลี่ยนไฟล์หรือปรับหน้าตัด/เหล็ก:

| Girder | Source Excel row | Tu (kN·m) | Model Tn รวม U + พื้น (kN·m) | Model Vn (kN) | Model nominal V–T D/C | สถานะ |
|---|---:|---:|---:|---:|---:|---|
| Interior Girder 2 | 556 | 286.8371 | 277.4754 | 1,437.5927 | 1.53577 | MODEL REVIEW |
| Left Exterior Girder | 237 | -190.3973 | 242.4266 | 1,318.6799 | 0.93828 | MODEL REVIEW |

## ตรวจสอบซอฟต์แวร์

- 157 selected tests ผ่าน รวม 8 tests ใหม่ของ primary model view / stale results / การคง nominal REVIEW ไม่ได้รันทั้ง repository
- เว้น 1 test เดิม `test_different_vectors_at_one_case_station_are_not_enveloped` ซึ่งมีปัญหา fixture concurrent declaration ใน baseline ก่อนหน้า โดยคง source guard เดิม
- ทดสอบ Calculate ใน app.py ด้วย Streamlit AppTest จริงทั้ง Torsion และ Shear + Torsion: primary overview และผลราย girder ตรงตัวเลขเดิม มี Reference panels และเปิดหน้าซ้ำไม่เรียก solver เพิ่ม
- ทดสอบส่วนแสดงโมเดลแยก: ไม่มีปุ่มหรือ checkbox เพิ่ม และไม่รัน solver จาก render
- JSON ต้นทางและค่าหน้าตัด/รอยต่อไม่เปลี่ยน ไม่เพิ่ม result-cache persistence
- py_compile ผ่าน app.py และทุก Python module ที่แก้/เพิ่ม
- ไม่ได้ตรวจ screenshot ใน browser จริง เพราะ environment ไม่มี browser binary; AppTest เป็นการตรวจ UI/runtime ไม่ใช่ screenshot QA หรือ structural validation

หลักฐาน: `qa/evidence/igird_modeltn47/` และ script ตรวจซ้ำ:

```bash
python qa/validate_modeltn47_project.py --project PATH_TO_PROJECT.json --output modeltn47_verification
```

## Repo summary

Make the stored U-plus-slab Model Tn/Vn and nominal concurrent V–T result the primary composite Analysis view; retain I-hoop reference checks, current-result hashes and source identities. Preserve CSI Tu, resistance equations, nominal review status and production acceptance separation. Reuse existing inputs and Calculate actions.
