# IGIRDER.COMPOSITE48 — ฐานพัฒนาต่อจาก MODELTN47

รุ่นนี้แก้ข้อบกพร่องที่ตรวจพบและคงโมเดลร่วม **เหล็กปลอก I + U สองขา + เหล็กยาวพื้น** ตามข้อมูลจริงใน JSON สำหรับ Model Vn, Model Tn และ nominal V–T พร้อมตรวจย้อนหลังทุกแถวแรงภายในช่วงคาน

**เป้าหมาย “full composite ที่ตรวจยืนยันครบสำหรับออกแบบจริง” ยังไม่สำเร็จในรุ่นนี้** การผ่าน numerical/software verification ไม่ใช่ structural validation ของวิธีกำลัง และไม่มีการเปลี่ยนผลเป็น design PASS โดยอาศัยคำยืนยันหรือ checkbox

## สิ่งที่แก้

1. แยกแหล่งข้อมูลเหล็กปลอกออกจากผล torsion threshold: ผล BELOW THRESHOLD มีสิทธิ์ไม่คืน Ao/ph/At หรือธง hook แต่ไม่ได้หมายความว่าเหล็กจริงหายไป รุ่นนี้อ่าน zone, closed-loop/hook qualification, Ao/ph, ขนาดเหล็ก, spacing และ fy จากหน้าตัดโดยตรง หากข้อมูลจริงไม่ผ่านยังบล็อกตามเดิม
2. คำนวณทุกแถวแรงร่วมภายในช่วงคาน แล้วเลือก maximum nominal V–T D/C ต่อ girder แทนการเลือกแถว |Tu| สูงสุดเพียงแถวเดียว ไม่ประกอบแรงจากคนละแถว และคง U1A/U1B/U2A/U2B, Max/Min, Before/After และเลขแถวต้นทาง
3. เพิ่มแถวควบคุม V-only และ T-only ที่คง M3/N จริง แยกจากค่า Model Vn/Tn ที่ M=N=0 ซึ่งเป็น intercept ตามนิยามเดิม การตรวจ V–T ยังคง M3/N จริงและเพิ่ม V2/T ด้วยตัวคูณเดียว
4. แสดงจำนวนแถวที่คำนวณได้/บล็อก/นอกขอบเขต หากมีแถวที่คำนวณไม่ได้ ผลรวมเป็น MODEL INCOMPLETE แม้แถวตัวเลขที่เลือกจะมี D/C ต่ำกว่า 1 กรณี demand ไม่เป็นศูนย์แต่ capacity เป็นศูนย์ไม่ถูกแสดงว่าอยู่ภายในกำลัง
5. ใช้โมเดลร่วมเป็นผลหลักในหน้า Shear, Torsion และ Shear + Torsion โดยเก็บ code checks และกราฟเดิมใน Reference checks เพิ่มความสัมพันธ์ของ input hash กับเหล็กปลอกสำหรับ composite Shear
6. เพิ่มการตรวจสมดุลในหน่วยจริงจาก saved witness โดยไม่ใช้เมทริกซ์ LP หรือเรียก solver ใหม่ และเพิ่มหลักฐานความพร้อมของวิธีคำนวณใน Calculation trace

## เหล็กที่นับและวิธีใช้กำลังร่วมกัน

- ปลอก I: ใช้หนึ่งขาต่อเทอม torsion และสองขาจริงต่อ shear ในเส้นทาง I เดิม
- U: สองขาของ independent dowel ใช้เพดานแรงของขาเดียวกันร่วมกับ V/T และการหนีบรอยต่อ จึงไม่บวกกำลังเต็มซ้ำ และไม่ถือ extended I-stirrups เป็น U ชุดอิสระอีกชุด
- เหล็กพื้น: ใช้ชั้นบน–ล่างจาก input เดิม พร้อมระยะพัฒนาแรงและการแบ่ง physical longitudinal pools เหล็กพื้นไม่กลายเป็นกำลังสำรองของ I-only path เมื่อตัด U ออก
- ค่า continuity/anchorage confirmation เดิมไม่ถูกเปลี่ยนเป็น true อัตโนมัติ การมีเหล็กใน inventory ไม่ได้พิสูจน์ว่าแรงจากทุกตำแหน่งกระจายเข้าถึงวง U ได้ครบ

สมการและข้อจำกัดหลักของ STEEL45 ยังเป็น fixed-angle cracked truss, Vc=0, cohesion=0, shared web-concrete flow และ assumed longitudinal allocation รุ่นนี้ไม่ได้ปรับตัวคูณเพื่อให้กำลังสูงขึ้นหรือบังคับผลผ่าน

## ผลจาก JSON โครงการ

ต้นทาง `concrete_section_pro_project_31_COVER38.json`; SHA-256 `0ae85f6de0b753062393a70717105953836a4a7722449edfbdc0e91ba8f99fcb`

มี 640 แถวจาก 2 girders และ 4 load cases คำนวณได้ครบ **608/608 แถวภายในช่วงคาน** ส่วน 32 แถวที่ x=0/L ระบุว่านอกขอบเขต interior model เพราะยังไม่มีวิธี bearing/transfer/diaphragm D-region resistance ของระบบนี้ จึงไม่ใช่ full-span design acceptance

| Girder | แถวภายใน | below threshold ที่กู้คืน | แถว V–T nominal > 1 | แถวควบคุม V–T |
|---|---:|---:|---:|---|
| Interior Girder 2 | 304 | 14 | 58 | x=2 m, U2A Min, Before, Excel 491 |
| Left Exterior Girder | 304 | 108 | 0 | x=18 m, U2A Min, After, Excel 237 |

| ผล ณ แถวควบคุม V–T | Interior Girder 2 | Left Exterior Girder |
|---|---:|---:|
| Model Vn, M=N=0 (kN) | 1396.909 | 1318.680 |
| Model Tn, M=N=0 (kN-m) | 263.883 | 242.427 |
| nominal V–T D/C, actual M3/N | 1.554338 | 0.938280 |
| สถานะ | EXCEEDS NOMINAL / MODEL REVIEW | WITHIN NOMINAL / MODEL REVIEW |

Interior Girder 2 เดิมเลือก x=18 m ซึ่งมี |Tu| สูงสุดและได้ D/C 1.535771 การตรวจทุกแถวพบว่า x=2 m ควบคุมมากกว่า ผลตัวเลขของ 486 แถวที่รุ่น 47 คำนวณได้ยังตรงกันทุกค่า แถวที่เดิมถูกบล็อกผิดทั้ง 122 แถวยืนยันว่าเป็น below threshold และคำนวณได้แล้ว

แถวควบคุมแยก action เมื่อคง M3/N จริง:

| Girder | V-only nominal D/C | T-only nominal D/C | V–T nominal D/C |
|---|---|---|---|
| Interior Girder 2 | 0.578000 @ x=2 m, Excel 491 | 0.979404 @ x=3 m, Excel 495 | 1.554338 @ x=2 m, Excel 491 |
| Left Exterior Girder | 0.656429 @ x=2 m, Excel 171 | 0.710456 @ x=17 m, Excel 233 | 0.938280 @ x=18 m, Excel 237 |

ค่าข้างต้นไม่มี φ และไม่ใช่การตรวจ LRFD ผ่าน/ไม่ผ่าน ห้ามบวก Vn+Tn เป็นจำนวนเดียวเพราะหน่วยต่างกัน V–T เป็นการตรวจการใช้กำลังร่วมกัน

Tu ทุกแถวคงค่าต้นทาง ณ จุดรายงานของ CSI ไม่ย้ายไป centroid คาน I ส่วน M2/M3 ยังคงการอ้างอิงของ bending reader ตามรุ่น 46/47 ข้อมูลแรง วัสดุ หน้าตัด และเหล็กใน JSON ไม่ถูกเปลี่ยน

## หลักฐานการตรวจซอฟต์แวร์

- 212 selected tests ผ่าน รวม 22 test cases ใหม่ ไม่ใช่การรันทั้ง repository
- ปรับ fixture เก่า 3 จุดที่ล้มเหลวซ้ำบน MODELTN47: ระบุ analytical static concurrency ให้ถูกต้อง และเปลี่ยนการตรวจ version เก่าเป็นการตรวจ stale-input hash จริง โดยไม่ผ่อน source gate ของข้อมูลโครงการ
- Full-bank replay: numeric residual สูงสุด 2.4693e-14; 608 แถวคง Tu ต้นทางทั้งหมด ใช้เวลาประมาณ 370 วินาทีใน runtime นี้
- Independent physical-unit audit: 5 source governors / 25 witnesses ผ่าน สมดุลแรง แรงบิด คู่แรงรอยต่อ และเพดานทรัพยากรที่ประกาศไว้; error สูงสุด 3.7753e-16
- ทดสอบ contact strips 8/16/32/64 ในกรณีรอยต่อควบคุม ทดสอบ steel monotonicity, zero/missing supplies และการป้องกันนับ U ซ้ำ
- AppTest ของ app.py: Calculate Shear/Torsion/Shear + Torsion ทั้งสอง girders จาก 4 original regression vectors ผ่าน ไม่มี solver เพิ่มเมื่อเปิดดูซ้ำ ไม่มีปุ่มหรือช่อง input เพิ่ม
- py_compile ของ app.py และ Python files ที่เปลี่ยนผ่าน
- ไม่มี browser binary จึงไม่ได้ตรวจ screenshot ใน browser จริง AppTest ไม่ได้ทดแทนหลักฐานส่วนนั้น

## สิ่งที่ยังต้องทำเพื่อ design acceptance

ปัญหาหลักอยู่ที่วิธีคำนวณ ไม่ใช่ให้ผู้ใช้กรอกช่องยืนยันเพิ่ม:

1. สร้าง stress field ของ I–slab–U ที่ตรวจสมดุลและกำลัง concrete strut/node, splitting, transverse slab transfer และการยึดเหนี่ยวของ U-hook/mesh จาก geometry จริงได้ เพดาน concrete-flow และการแบ่ง longitudinal pool ปัจจุบันยังไม่ใช่ safe lower-bound ที่พิสูจน์สำหรับโครงสร้างจริง
2. สร้าง resistance equilibrium เกี่ยวกับจุดรายงาน CSI เดิมให้ครอบคลุมแรงที่จำเป็น รวม M2/V3 หรือพิสูจน์ขอบเขตการละเลย โดยรักษา Tu input เดิม การไม่ย้าย Tu ไม่ได้ทำให้โมเดล resistance มีจุดอ้างอิงสอดคล้องโดยอัตโนมัติ
3. กำหนด resistance factors และ failure modes ของวิธีร่วมที่มีฐานมาตรฐานรองรับ พร้อมตรวจ end D-regions และเงื่อนไขใช้งาน ไม่มีการใส่ φ ให้โมเดลทดลองโดยพลการ
4. เทียบกับ analytical limits และผลทดลองอิสระที่ครอบคลุม closed-path/interface behavior และแรงร่วม กำหนดเกณฑ์/ขอบเขตก่อนเทียบผล ไม่ปรับ fit แล้วเรียกข้อมูลเดิมว่า independent validation

วิธี strength design ที่มี stress field/STM ครบและใช้ตามขอบเขตมาตรฐานอาจไม่ต้องใช้ nonlinear strain/slip solver เต็มรูปแบบทุกกรณี ดังนั้น “ขาด strain/slip” ไม่ใช่เหตุผลเดียวที่จะปิดทางพัฒนา แต่ LP ปัจจุบันยังขาด concrete/nodal justification ที่จำเป็นในการอ้างวิธีดังกล่าว

## งานค้นคว้าที่ตรวจเพิ่ม

- Zhang, Wang & Lin, *Experimental Investigation on Torsional Behavior of Composite Beams Reinforced with Two-Piece Enclosed Stirrups*, 2017 MOC & ISICT, pp.148–156. ทดสอบ rectangular RC 150×250 mm ภายใต้ pure torsion; detail ใช้ U + crosstie พร้อม 135° hooks และเตรียมผิวรอยต่อ งานนี้สนับสนุน composite torque transfer ภายใต้รายละเอียดที่ทดสอบ แต่ไม่ได้ยืนยัน I-girder/U-hook 90° และ concurrent V–T ของโครงการ: https://edocs.tib.eu/files/e01mr23/1840320877.pdf
- Li et al., 2020, DOI 10.14006/j.jzjgxb.2019.0005. ทดสอบ overlapping hoops และเปรียบเทียบ hook 90°/135° พบความแตกต่างด้าน post-peak ductility จึงไม่ถือทั้งสองรายละเอียดเทียบเท่ากันโดยอัตโนมัติ: https://repository.lsu.edu/mechanical_engineering_pubs/1582/
- FHWA-NHI-17-071 (2017), *Strut-and-Tie Modeling for Concrete Structures, Design Examples*; ร่วมกับ AASHTO LRFD 9th Ed. 5.8.2 ที่ผู้ใช้ให้มา ใช้เป็นหลักการตรวจ strut/tie/node/anchorage ไม่ใช่ใบรับรองของโมเดลนี้: https://www.fhwa.dot.gov/bridge/concrete/nhi17071.pdf

## วิธีใช้และฐานพัฒนาต่อ

ใช้ ZIP COMPOSITE48 เป็นฐานพัฒนาต่อ โหลด JSON เดิม แล้วใช้ Calculate ปุ่มเดิมใน Shear, Torsion หรือ Shear + Torsion ตารางหลักแสดงแถวควบคุม V–T และตารางถัดมาแสดงแถวควบคุมแยก V/T/VT เปิด Source rows / Scan coverage เพื่อตรวจทุกแถวและ end exclusions

Calculation trace แสดง inventory, physical hoop source, equations, witness และ design evidence ข้อมูลการคำนวณยังอยู่ใน session แยกจาก production cache / Result Summary / Report / QA ซึ่งใช้ code-check route เดิม และไม่มี solver ทำงานจากหน้าอ่านผล

Repo summary: Continue MODELTN47 as COMPOSITE48; fix threshold-dependent hoop loss, scan concurrent source rows and select actual V–T governors, retain I/U/slab shared supplies and raw CSI Tu, add verification evidence without claiming design validation.
