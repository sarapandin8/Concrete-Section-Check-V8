> Historical milestone: CSITU46 now uses reported CSI Tu unchanged for Torsion/V–T. See `IGIRDER_CSITU46_HANDOFF_TH.md`; centroid-torque values below describe the earlier release.

# IGIRDER.STEEL45 — นับ U-dowel และเหล็กยาวพื้นในโมเดลร่วม V / T

**เพิ่มการคำนวณ Vn, Tn และ V–T ที่ใช้ U สองขาและเหล็กยาวพื้นแล้ว แต่ยังเป็น MODEL REVIEW ไม่ใช่ full composite resistance ที่ตรวจยืนยันสำหรับออกแบบ ผลกำลังตามมาตรฐานเดิมยังแยกและไม่ถูกแทนที่**

## ใช้งาน

1. เปิด Project JSON เดิม ข้อมูลขา U และ Slab mesh ใช้ชุดเดิม ไม่ต้องกรอกแบบฟอร์มใหม่
2. ไป Analysis → Shear, Torsion หรือ Shear + Torsion แล้วกด Calculate ปุ่มเดิม หากใช้ collection ให้กดปุ่ม Calculate ของ collection
3. เปิดแผง Girder ที่ต้องการดู ใต้ผลเดิมจะมี **Composite reinforcement — I-girder, U-dowel and slab**
4. อ่านสามแถว: With U + slab steel, Same model without U และ Same model without slab longitudinal steel ส่วน Calculation trace แสดง ledger ของเหล็กและสมการ

โมเดลเลือกหนึ่งแถวแรง concurrent ที่ |Tu หลังย้ายไป centroid คาน| สูงสุดต่อ Girder โดยยกเว้น x=0/L ตารางบอก station/case ที่ใช้ชัดเจน ไม่ได้ตรวจ envelope กำลังระบบร่วมทั้งช่วงคาน และแถวที่เลือกอาจต่างจากกรณีวิกฤตของผลตามมาตรฐาน

## สิ่งที่คำนวณเพิ่ม

- ขา U สองขามาจาก connector source จริง ขนาด/ระยะเรียงตาม zone เดิม หากเลือก I-hoop extended into slab ซึ่งเป็นเหล็กชุดเดียวกัน โมเดลจะไม่สร้าง U ชุดที่สองมานับซ้ำ
- เส้นทาง I-hoop กับ U–slab ใช้ Ao คนละค่า ตัว I ยังคง Ao เดิม ส่วน U ใช้เซลล์กลางรูปสี่เหลี่ยม a×H เป็นสมมติฐานของการปิดผ่านพื้น ไม่ได้อ้างว่าเป็น closed-hoop geometry ที่ยืนยันจากแบบแล้ว
- ตัวแปรแรงของ U แต่ละขามีชุดเดียว ทั้งสำหรับ V/T และการหนีบรอยต่อ/แรงเสียดทาน การคำนวณไม่ได้บวกกำลัง Tn สองระบบหรือบวกสองขาเป็น At ของปลอกปิดเดิม
- เหล็กยาวพื้นบน–ล่างใช้พื้นที่เทียบเท่าตาม Be/db/spacing และตำแหน่ง cover เดิม คำนวณระยะพัฒนาแรงจากช่วง start/end ที่กรอก โดยมีสมมติฐานความต่อเนื่องภายในช่วงนั้น ค่า confirmation เดิมใน JSON ไม่ถูกเปลี่ยนเป็น true
- เหล็กยาวทุกชั้นอยู่ใน pool บน/ล่างตามพิกัดจริง เหล็กพื้นทั้งสอง mat ของโครงการนี้อยู่ในครึ่งบนของหน้าตัดรวม จึงไม่ถูกโยกไปเพิ่มกำลังเหล็กยาวด้านล่างแบบตรง ๆ
- ใช้งบคอนกรีตส่วนที่ทับซ้อนเพียงครั้งเดียว รวมข้อจำกัดปลอก I, U, เหล็กปิดในพื้น, เหล็กยาว และรอยต่อในปัญหาสมดุลเดียว มี primal/dual และ resource witness ตรวจย้อน

## ผลจาก JSON โครงการ

ไฟล์ต้นทาง: `concrete_section_pro_project_31_COVER38.json`  
SHA256: `0ae85f6de0b753062393a70717105953836a4a7722449edfbdc0e91ba8f99fcb`

ตัวอย่าง U2A ที่ x=18 ม. ตัวเลขต่อไปนี้เป็น **nominal intercept / fixed-angle model** เทียบภายใน STEEL45 เท่านั้น ไม่มีค่า phi สำหรับยอมรับการออกแบบ

| Girder | รายการ | โมเดลเดียวกันไม่รวม U | รวม U + เหล็กพื้น | ผลต่าง |
|---|---|---:|---:|---:|
| BOBJ1 / Interior Girder 2 | Model Vn (kN) | 1,349.53 | 1,484.25 | +9.98% |
| BOBJ1 / Interior Girder 2 | Model Tn (kN·m) | 276.37 | 292.92 | +5.99% |
| BOBJ1 / Interior Girder 2 | Model nominal V–T D/C | 2.272 | 2.066 | -9.08% |
| BOBJ1 / Left Exterior Girder | Model Vn (kN) | 1,424.21 | 1,424.21 | +0.00% |
| BOBJ1 / Left Exterior Girder | Model Tn (kN·m) | 244.28 | 272.70 | +11.63% |
| BOBJ1 / Left Exterior Girder | Model nominal V–T D/C | 1.572 | 1.572 | +0.00% |

ทั้งสองตัวอย่างยังเกินขอบเขตโมเดลที่แรง V–T จริง (D/C>1) ตัวอย่างนี้นับเหล็กยาวพื้น 2,814.867 ตร.มม. เป็นกำลังดึง nominal ตาม development ประมาณ 1,097.798 kN การตัดเหล็กยาวพื้นออกทำให้เส้นทาง U–พื้นไม่ได้รับเครดิตในโมเดลนี้ บางตำแหน่งเพิ่ม U แล้ว Vn หรือ V–T ไม่เพิ่ม เพราะข้อจำกัดอื่นคุมอยู่

**อย่าเทียบ Vn ตารางนี้ตรงกับผล COMPARISON44/ผลมาตรฐานเดิม:** STEEL45 ใช้ fully cracked truss, Vc=0 และ theta คงที่จากแถว concurrent เดิม ส่วน General Procedure เดิมมี Vc และ theta ของการตรวจแต่ละชนิด ผลตรวจเดิม Interior Girder 2 ที่ x=18 ม. ยังคง Vn=2,325.95 kN, Tn สาขาเหล็กขวาง=275.95 kN·m และ V–T D/C=2.526 ไม่ถูกแทนด้วยตัวเลขโมเดล

รายละเอียด U ที่ใช้ตามไฟล์นี้: DB12 สองขา @100 มม. ณ x=18 ม., a=100 มม., F=1,400 มม., B=200 มม., E=150 มม., D=72 มม. ค่า E นี้มาจาก JSON ปัจจุบัน แม้ก่อนหน้านี้เคยคุย E=170 มม. ไม่ได้เปลี่ยนค่าเพื่อให้ผ่าน หากแก้ E เป็น 170 จะเหลือ B=180 มม. และต้องให้ anchorage check ประเมินใหม่ ไม่ควรถือว่าพัฒนาแรงเต็มได้อัตโนมัติ

## ขอบเขตที่ยังไม่เสร็จ

1. เส้นทาง U–พื้นปิดผ่าน anchorage zone/mesh เป็นสมมติฐาน ไม่ใช่ข้อพิสูจน์จาก hook 90° หรือการผูกเหล็กเป็นตะแกรง AASHTO 2020 §5.10.8.2.6d กำหนด transverse torsion reinforcement ให้ fully continuous และยึดด้วย hook 135° รอบเหล็กยาว การผ่าน tension-hook development ไม่ทดแทนเงื่อนไขนี้
2. ใช้ทิศ diagonal คงที่, ความต้านคอนกรีตแบบกำหนดเพดาน และ Coulomb contact ไม่มี law ของ cracked concrete/bond/slip ที่สอบเทียบ โมเดลนี้อาจประเมินกำลังสูงหรือต่ำกว่าจริงได้ ยังไม่ใช่ lower-bound proof ของโครงสร้างจริง
3. คอนกรีตส่วนทับซ้อนใช้ q limit = 0.25 f'c,g bv/[2(cotθ+tanθ)] เป็น **model assumption** เหล็กปิดในพื้นใช้ mat ที่ให้ supply ต่ำกว่า ไม่ใช่การรับรอง nodal faces, splitting, confinement หรือ anchorage ของ mat
4. pure Model Vn/Tn ใช้ M=N=0 ส่วน Model V–T ขยาย V2/T และคง M3/N ตามแถวต้นทาง การตรวจ M2/V3 เต็มระบบยังไม่รวม แม้เก็บแรงดิบครบและใช้ V3 ใน torque transport
5. ไม่มี independent structural validation ของ I-girder + precast/CIP joint + U + slab ของโครงการ จึงไม่มี accepted Vn/Tn/V–T และไม่มีตัวเลือกให้บังคับ PASS

ผลใหม่อยู่ใน review runtime แยกต่างหาก ล้างเมื่อปิด session และไม่เขียนเป็นกำลังยอมรับใน production cache, Summary, Report/QA หรือ Project JSON ค่า Loads, rebar/strand positions และ input declarations เดิมยังคงเดิม

## การตรวจซอฟต์แวร์

- 116 tests ที่เลือกผ่าน รวม 17 tests ใหม่ของ STEEL45 ข้อจำกัด: ไม่ได้รันทั้ง repository
- 1 test เดิม `test_different_vectors_at_one_case_station_are_not_enveloped` ล้มเหลวเหมือนกันใน REFERENCE43 ภายใต้ environment เดียวกัน เพราะ fixture ไม่ผ่าน concurrent-source gate จึงไม่มี `Mu kN-m` คัดออกจากชุด 116 ข้างต้น ไม่ได้แก้หรืออ้างว่าผ่าน
- Project integration ผ่านทั้ง Shear, Torsion และ Shear + Torsion สำหรับ 2 Girder: source vector, U supply bounds, review-cache separation, stale lookup และ input-only JSON
- ผลมาตรฐานเดิมเท่ากันครบ 12 station/case pairs (6 ตำแหน่ง × composite on/off) เทียบกับ COMPARISON44
- `py_compile` ผ่าน app.py และไฟล์ที่แก้/เพิ่ม
- Streamlit AppTest ของแผงใหม่ผ่าน แสดง warning, ตารางผล และ ledger ไม่มีปุ่ม Run หรือ checkbox ใหม่
- ยังไม่ได้ตรวจ screenshot ใน browser จริง: environment ไม่มี browser binary และการดาวน์โหลด browser ล้มเหลว จึงไม่อ้างว่าผ่าน visual/browser QA

รันซ้ำจาก root ของ repo ด้วย environment ตาม requirements.txt:

```bash
python qa/validate_steel45_project.py --project PATH_TO_PROJECT.json --station 18 --output steel45_results
```

ชุดผลเต็มอยู่ใน `qa/evidence/igird_steel45/` และแยกให้ดาวน์โหลดเป็น JSON ด้วย

## Repo summary

Add a separate composite V/T review with shared U-leg, slab-mat and longitudinal-steel resources, source-preserving input reuse, numerical witnesses and isolated runtime storage. Preserve production resistance gates; full composite design acceptance remains unvalidated.
