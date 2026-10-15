# IGIRDER.JOINT29 — U-dowel anchorage และกลไกรอยต่อรับแรงเฉือน–เปิด–บิด

วันที่ 15 ตุลาคม 2026 · พัฒนาต่อจาก DOWEL28 ที่ส่งมอบแล้ว

เพิ่มการตรวจ U-dowel ใน Analysis ทั้งระยะฝังยึดและสมดุลของรอยต่อหลังแตกร้าว เพื่อพิจารณาบทบาทถ่ายแรงบิดผ่านคู่แรงดึงใน dowel กับแรงอัดสัมผัสในคอนกรีต ร่วมกับแรงเฉือนที่รอยต่อ เหล็กชุดเดียวถูกใช้ในสมดุลร่วมกัน จึงไม่ถูกให้กำลังเต็มแยกซ้ำสำหรับแรงเปิดและแรงเฉือน

**รุ่นนี้เป็นการตรวจกลไกเฉพาะรอยต่อ ยังไม่ใช่ full composite shear–torsion resistance แม้กรอกข้อมูลครบและกลไกคำนวณได้ ก็ยังคงสถานะรวม REVIEW และไม่เพิ่ม Ao/ph หรือเปลี่ยนผลกำลัง ULS เดิมจากผลทดสอบกลไกนี้**

## สิ่งที่เพิ่มและแก้

- คำนวณ standard 90° tension-hook development ใน slab และ straight vertical development ใน girder ตาม AASHTO LRFD 9th Edition (2020) พร้อมตรวจปลายตรง วงดัด และการใส่ได้จริงในความหนา slab / ความสูงคาน
- ตรวจแนวขา U ทั้งสองกับ polygon หน้าตัดจริงตลอดระยะฝัง รวมบริเวณ web แคบและช่องว่างภายใน โดยคง clear cover ที่กำหนด รอยต่อที่ slab หล่อทับไม่ถูกนับเป็นผิวอิสระสำหรับ cover
- เพิ่มแบบจำลองรอยต่อหลังแตกร้าว มีสองแถวขาเหล็กสมมาตร คอนกรีตรับอัดอย่างเดียว และ friction พร้อมหาตัวคูณแรงร่วมที่ขีดจำกัดของแบบจำลอง
- รับ joint actions แยกเป็นแรงเฉือนตามยาว qx, ตามขวาง qy, แรงเปิด n และ roll moment mx ต่อความยาวสมาชิก 1 m พร้อม Case/Source/Station ของสถานะเดียวกัน ค่าที่ไม่ทราบยังเป็น null ไม่แปลงเป็นศูนย์และไม่ใช้ Girder Tu แทน
- เพิ่มผลสรุปและ Calculation trace / Equations, พยานสมดุลแรงที่ขีดจำกัด และดาวน์โหลด CSV ภายใน Analysis โดยคงผลไว้นอก production ULS / Summary / Report-QA
- แก้ข้อความการ์ด Avf เดิมให้สะท้อนแหล่งเหล็กที่เลือกและคำประกาศ anchorage ทั่วไป แทนการอ้างตารางปลอก I เสมอเมื่อใช้ dowel

## วิธีใช้

เปิดชุดแอปใหม่ด้วย `streamlit run app.py` และเปิด `I_Girder_20m_JOINT29_DRAFT.json` ตัวอัปโหลด ULS/SLS และ raw Loads ของเดิมใช้เหมือนเดิม

1. ที่ Analysis → ULS → Flexure → Final — Composite เปิดรายละเอียด Final Composite หากอยู่ใน compact view
2. ตาราง Dowel layout ยังคง DB12 @70/@150/@200 และช่อง Start/End x ที่ผู้ใช้เลือกกรอกแยกเอง กรอกช่วงตามแบบตามยาวก่อนใช้ผลตามสถานี
3. เปิด `U-dowel torque transfer — mechanism inputs` ซึ่ง DRAFT เลือก `Cracked interface — equilibrium screening` ไว้แล้ว ระบุ coating และ anchorage region จริง
4. กรอกระยะศูนย์กลางขา U ตามขวาง, ldh ที่มีใน slab, ปลายตรงหลังโค้ง, เส้นผ่านศูนย์กลางวงดัดด้านใน, cover ที่โครงการกำหนด และความยาวขาตรงที่ยึดเหนี่ยวใน girder โดยไม่นับส่วนโค้ง U ด้านล่าง
5. หากมีผลแรงรอยต่อจาก free-body หรือ FE interface reactions ให้ใส่หนึ่งสถานะพร้อมกันต่อแถวใน `Interface actions per metre of member` แล้วกด `Calculate U-dowel Joint` การเปิดแผงหรือแก้ช่องไม่รันตัวคำนวณเอง

มีเพียง checkbox คำประกาศ crossing/anchorage เดิม ไม่มี checkbox ยืนยันใหม่ คำประกาศเดิมเพียงอย่างเดียวไม่แทนการตรวจมิติในโมดูลใหม่

## ความหมายของข้อมูลรอยต่อ

| ช่อง | ความหมาย / หน่วย |
|---|---|
| Station x | สถานีบนแกน Loads เดิม หน่วย m ภายในปลายคานจริง |
| qx | แรงเฉือนตามยาวบนระนาบรอยต่อ kN/m ของความยาวคาน |
| qy | แรงเฉือนตามขวางบนระนาบรอยต่อ kN/m ของความยาวคาน |
| n | แรงตั้งฉากรอยต่อ kN/m; ค่าบวกเปิดรอยต่อ |
| mx | โมเมนต์ต้านการหมุนระหว่าง slab/girder เกี่ยวกับศูนย์กลางรอยต่อ kN-m/m ของความยาวคาน |
| Case / Source | ระบุสถานะและที่มาของ joint action vector เดียวกัน ไม่ใช่ extrema ที่นำมาผสม |

mx ข้างต้นเป็นการถ่ายโมเมนต์ผ่านรอยต่อบนช่วงย่อยที่พิจารณา ไม่เท่ากับค่า Tu รวมของ Girder โดยทั่วไป การหา mx ต้องรวมแรงกระทำภายนอกบนชิ้นส่วนและสมดุลของ slab/girder ด้วย จึงยังไม่มีการหา mx อัตโนมัติจาก force resultants ที่มีอยู่เพียงอย่างเดียว

แบบจำลองใช้สองแถวขา U ที่สมมาตรรอบศูนย์กลางรอยต่อ และหนึ่ง U มีสองขาข้ามรอยต่อ ไม่ได้รองรับการเฉลี่ยจำนวนขา 4/6/8 เป็นสองแถวโดยอัตโนมัติ จุดเปลี่ยน dowel zone ที่มีสองรายการครอบคลุมสถานีเดียวกันจะตรวจทั้งสอง candidate แยกกัน ไม่รวมกำลังและไม่เลือกจาก Avf อย่างเดียว เพราะขนาดเหล็กต่างกันอาจมีผลต่อระยะฝัง

## การฝังยึดและข้อมูลจากรูป

ใช้ general tension-hook route ที่อนุรักษนิยม: ปลายตรง 12db, วงดัดทั่วไป 6db สำหรับ db≤25.4 mm และ 8db สำหรับขนาดที่ใหญ่กว่าภายในขอบเขตที่รองรับ ไม่ใช้ alternative shear-stirrup anchorage route ซึ่งต้องมีรายละเอียดโอบเหล็กตามยาวและข้อกำหนดของตัวเอง การไม่ผ่าน route นี้จึงไม่ใช่ข้อสรุปว่ารายละเอียดนั้นไม่ผ่านทุกวิธีที่มาตรฐานยอมรับ

ให้ lambda_rc = lambda_er = 1 ไม่ลดด้วย confinement หรือ excess reinforcement ใช้ location factor ของขาตั้ง และไม่ให้เครดิตโค้ง U ด้านล่างแทน straight development เหล็ก epoxy ใช้ factor 1.2 สำหรับ hook และ 1.5 สำหรับขาตรง ซึ่งเป็นกรณีอนุรักษนิยมของ cover/spacing

| โครงการปัจจุบัน DB12 fy390 | ไม่เคลือบ | Epoxy |
|---|---:|---:|
| ldh ที่ต้องการใน slab fc35 | 190.803 mm | 228.963 mm |
| ld ขาตรงที่ต้องการใน girder fc45 | 637.663 mm | 956.495 mm |
| ปลายตรงทั่วไปที่ต้องการ | 144 mm | 144 mm |
| เส้นผ่านศูนย์กลางวงดัดด้านในทั่วไปที่ต้องการ | 72 mm | 72 mm |

ตัวเลขเป็น required lengths ภายใต้ route และตัวคูณข้างต้น ยังไม่ใช่ผลยืนยัน anchorage ของแบบจริง รูปที่ให้แสดง projection 250 mm และมิติแนวนอน 220 mm แต่ยังต้องแยกระยะวัดถึงนอกวงดัด ปลายตรง และวงดัดให้ตรงนิยาม DRAFT จึงเก็บมิติสองค่านี้เป็น reference เท่านั้น ไม่ใช้เป็น measured anchorage หรือระยะระหว่างขา U อัตโนมัติ

โครงการปัจจุบันมี Tslab = 350 mm ไม่ได้ปรับความหนา slab ใหม่ในรุ่นนี้ Required cover 50 mm ถูกใช้ซ้ำจากค่าชั้นบนของ slab เดิมเพื่อเป็น input เริ่มต้น ผู้ใช้ต้องให้ค่าที่ครอบคลุมข้อกำหนดจริงของทั้งสองส่วน

ขอบเขตตัวคำนวณ anchorage นี้คือเหล็กเดี่ยวแนวตั้ง db≤35.8 mm, fy≤75 ksi, คอนกรีต normal-weight ที่มีฐานข้อมูล density ทั้งสองส่วน และ fc≤10 ksi บริเวณ interior ยังไม่รองรับรายละเอียด hook ที่ discontinuous end, bundled bars หรือข้อกำหนด confinement เพิ่มเติมสำหรับ fc/fy สูงกว่าเกณฑ์ดังกล่าว กรณีนอกขอบเขตคง REVIEW

การประเมิน hook เป็น tension tie สำหรับการถ่ายแรงที่รอยต่อ แยกจากการจัดเป็น transverse torsion reinforcement โดยตรง ข้อ 5.10.8.2.6d กำหนดความต่อเนื่องเต็มและ hook 135° รอบเหล็กตามยาวสำหรับเหล็กปลอกบิด ยังไม่มีการรับรองให้ U ที่ปลาย 90° ในรูปเป็น closed torsion cage ของหน้าตัดรวม

## สมการกลไกรอยต่อ

แบ่ง contact width เป็น 64 แถบ ความดันอัดในแต่ละแถบคงที่ที่ centroid ของแถบนั้น ให้ Ti คือแรงดึงในสองแถวขาเหล็ก, Cj คือแรงอัดสัมผัส และ Sj คือแรงเสียดทานรวมทิศเดียวกับ resultant ของ qx/qy สำหรับแถบยาว 1 m:

```text
sum(Ti) − sum(Cj) = lambda n
sum(yi Ti) − sum(yj Cj) = lambda mx
sum(Sj) = lambda sqrt(qx² + qy²)
0 ≤ Sj ≤ mu Cj
sum(Sj) ≤ mu sum(Ti)             // ไม่เพิ่มเครดิต friction จาก external compression; Pc=0
```

กำหนดกำลัง Ti ต่อแถว = 0.90 × (Avf/2) × min(fy,60 ksi) ใช้ area/force units ให้ตรงกัน ส่วนกำลังอัดสัมผัสใช้ 0.70 × 0.85fc ของคอนกรีตด้านอ่อนกว่า โดยไม่เพิ่ม bearing area factor และกำลังเฉือนคอนกรีตต่อแถบจำกัดที่ 0.90 × min(K1fc,K2) × พื้นที่แถบ ให้ cohesion = 0 สำหรับแบบจำลองรอยต่อหลังแตกร้าวนี้

ตัวคำนวณ maximize lambda ด้วย SciPy/HiGHS linear programming และตรวจพยานสมดุล/ขอบเขตแรงซ้ำก่อนแสดงผล D/C = 1/lambda เป็น radial utilization ของ joint action vector ที่กำหนด ทุกองค์ประกอบของ vector ถูกเพิ่มพร้อมกัน ไม่ใช่ค่า phiTn ของ Girder หรือ interaction surface เต็มของหน้าตัด

แรง Ti ชุดเดียวสร้างทั้งคู่แรงต้านการหมุน แรงต้านการเปิด และแรงบีบรอยต่อสำหรับ friction จึงไม่มีการให้พื้นที่เหล็กเต็มแยกซ้ำสำหรับแต่ละหน้าที่ ขณะเดียวกันยังไม่ให้เครดิต dowel bending/shear แยกเพิ่มจาก friction

ผล `WITHIN IDEALIZED MECHANISM`, `EXCEEDS IDEALIZED MECHANISM` หรือ `ZERO ACTIONS` เป็นผลของ constitutive model ที่สมมติไว้เท่านั้น ผลเกินกลไกแสดง D/C>1 และข้อมูลควบคุม แต่ทุกแถวยังคง composite-design status = REVIEW เพราะแบบจำลองสมดุลนี้ยังไม่พิสูจน์ strain/slip/opening compatibility, slab bending, splitting/local confinement หรือความเป็น lower bound ของสะพานจริง

ตัวแบบเฉลี่ยเหล็กเป็นปริมาณต่อ 1 m ไม่ใช่การตรวจ anchor group แต่ละตัวใน D-region หรือแรงกระจุกที่ diaphragm / bearing

## การตรวจสอบ

- Compile app.py และโมดูลที่เพิ่ม/แก้ผ่าน
- ชุด targeted/regression ผ่าน **251 รายการ** รวม **40 cases ใหม่** ใน test_igird_joint29.py ไม่มี failure/error/skip
- ครอบคลุม required development lengths, epoxy factors, geometry fit, web/void cover, missing inputs, source/domain guards, zero actions, force/moment signs, code-edition scope, numerical solver failure, ไม่ให้ compression clamping credit, ไม่ใช้ Tu แทน joint mx, และ JSON null/input persistence
- Pure shear และ pure opening ของโจทย์สมมติแต่ละกรณีได้ lambda = 5.2929553028; เมื่อเปิดและเฉือนร่วมกันโดยใช้แรงอย่างละ 100 kN/m ได้ lambda = 2.6464776514 ตรงกับสมการแรงเหล็กร่วม N + V/mu ≤ phi As fy
- Pure-roll สมมติ: แบบ pressure block ต่อเนื่องได้ 152.062278 kN-m/m; mesh 32/64/128 ได้ 151.223511 / 151.874262 / 152.006467 kN-m/m ตามลำดับ ตัวเลขนี้เป็น mathematical benchmark ของแบบจำลอง ไม่ใช่กำลังของโครงการ
- ทดสอบ adapter ด้วยรูป I/material ของโครงการจริงและ inputs สมมติที่ติดป้าย QA ONLY: ขาเหล็กอยู่ใน web และได้คำตอบแรงร่วมตรง closed form โดยไม่เขียนสมมติฐานเหล่านั้นลง DRAFT หรือ production results
- Full app.py ผ่าน Streamlit AppTest: เปิด Final Composite, กด Calculate U-dowel Joint หนึ่งครั้ง, เก็บผลแยก, เปิด Summary/Report แล้วไม่ rerun และไม่เปลี่ยน raw Loads หรือ production ULS results; solver witness ไม่ถูกบันทึกใน Project JSON
- ยังไม่มี browser screenshot verification สำหรับแผงนี้ ไม่ได้อ้าง full-repository suite PASS และไม่ได้แก้ข้อไม่ผ่านเดิม 7 ข้อที่บันทึกใน CSIREF26
- ทดสอบบน Python 3.12 / SciPy 1.17.0; เพิ่ม dependency scipy>=1.13,<2 ใน requirements.txt

หลักฐานอยู่ที่ `qa/evidence/igird_joint29/` และสคริปต์ `qa/igird_joint29_actual_review.py`

สำหรับรันชุดใหม่และ DOWEL28 ซ้ำ ให้ preload Streamlit ก่อน pytest เพื่อใช้ runtime จริงแทน import-only fallback ใน conftest เดิม:

```bash
python -c 'import streamlit,pytest; raise SystemExit(pytest.main(["-q","tests/test_igird_joint29.py","tests/test_igird_dowel28.py"]))'
```

## ข้อมูลใน DRAFT และสถานะงานเต็ม

DRAFT คง Loads, CSI reference snapshots, geometry/materials, longitudinal slab bars และ I-stirrups เดิม เก็บเฉพาะ inputs ใหม่ไว้ใน metadata.dowel_connection ภายใต้ interface settings ไม่มี analysis-result persistence เพิ่ม ตัวเลขมิติที่ยังไม่ได้ยืนยันยังเป็น null, coating/region เป็น unknown, joint action table ว่าง และช่วง C/D/E ยังไม่เดาความยาว

การแก้เฉพาะ inputs ของ mechanism review จะทำให้ผลกลไกเดิม stale โดยไม่ล้างผล ULS เดิม ส่วนการแก้แหล่งเหล็กหรือข้อมูลรอยต่อที่ใช้ใน production interface check ยังคง invalidate ULS ตาม DOWEL28 ผล numerical screening ไม่ป้อนเข้า Summary/Report-QA หรือ production acceptance

สูตรกำลัง ULS/SLS เดิมและวิธีนำเข้า Loads ไม่ถูกเปลี่ยน รุ่นนี้เพิ่มสมการเฉพาะ module ใหม่และแก้คำอธิบายแหล่ง Avf ใน UI เท่านั้น

Full composite V2/V3/T และ P–M2–M3 ยังไม่เสร็จ ขั้นถัดไปต้องหา joint-action demand ที่มีที่มาชัด เชื่อมการกระจายแรงกับ deformation compatibility และรายละเอียด slab/เหล็กตามยาว/ปลอกปิด พร้อมตรวจสอบด้วย benchmark/ผลทดสอบที่ครอบคลุม ก่อนเปิดเป็นผลกำลังหน้าตัดรวมสำหรับงานออกแบบ ผล FE เชิงเส้นใช้ตรวจ demand/equilibrium ได้ แต่ไม่ใช่หลักฐานยืนยัน ultimate resistance ของแบบจำลองใหม่นี้

อ้างอิง: AASHTO LRFD 9th Edition (2020) ข้อ 5.5.4.2.1, 5.6.5, 5.7.4, 5.10.2 และ 5.10.8.2 จากเอกสารโครงการ; [FHWA PSC girder interface-shear example](https://www.fhwa.dot.gov/bridge/lrfd/pscus057.cfm) เป็นตัวอย่างฉบับเก่าสำหรับหลัก shear-friction; [SciPy linprog documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.linprog.html) สำหรับ numerical API มิใช่การรับรองแบบจำลองโครงสร้าง

Repo summary:

```text
IGIRDER.JOINT29: Add U-dowel anchorage and joint shear–opening–roll screening; enforce shared steel capacity and leg cover; preserve Loads/ULS. 251 selected tests passed; full composite V–T remains REVIEW.
```
