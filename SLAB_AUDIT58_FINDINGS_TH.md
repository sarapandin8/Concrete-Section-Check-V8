# SLAB.AUDIT58 — ตรวจสอบ D/C จาก JSON32 และผล CSiBridge

วันที่ตรวจ: 19 ตุลาคม 2026 · พัฒนาต่อจาก SLAB.REVIEW57 ที่ส่งมอบล่าสุด

พบข้อบกพร่องในแบบจำลองเดิมจริง: การบวกแรงดึงจากแรงเฉือนเต็มจำนวนให้ทั้งผิวบนและล่างโดยอัตโนมัติ ไม่ใช่การตรวจ interaction ของ shell ที่ตรวจยืนยันแล้ว การแก้ครั้งนี้ถอนส่วนเพิ่มนั้นออกจาก As ของ N–M และแสดงการตรวจแรงเฉือนแยกต่างหาก การลดตัวเลขจึงเป็นการแก้ขอบเขตและสมการของผลที่รายงาน ไม่ใช่หลักฐานว่าหน้าตัดผ่านภายใต้ N–M–V แล้ว

## ข้อมูลที่ตรวจและรันซ้ำ

- JSON: `concrete_section_pro_project (32).json`; ภาพผลเดิม: `slab results.pdf`
- Excel ต้นทาง: `Element Forces - Area Shells.xlsx`, `TABLE Objects And Elements - Areas(1).xlsx`, `Area Assigment.xlsx`, `Connectivity Data.xlsx`
- แรงต้นทาง 170,240 แถว; Top Slab ที่ตรวจ 146,432 แถว / 4,576 elements
- U1A, U1B, U2A, U2B ทั้ง Max/Min รวม 8 กลุ่ม กลุ่มละ 18,304 corner records ครบตาม geometry
- ใช้แรงทั้งแปดองค์ประกอบของแต่ละ source row ตามฐานข้อมูลแรงร่วมที่ผู้ใช้ยืนยันไว้
- พื้น f′c = 35 MPa; ความหนาที่ corner จาก CSiBridge 200–350 มม.
- เหล็กยาวบน DB16@200: As = 1,005.31 มม²/ม.; อีกสามชั้น DB16@150: As = 1,340.41 มม²/ม.; fy = 390 MPa
- Cover ใสของเหล็กขวาง 40 มม.; เหล็กยาวด้านใน 56 มม.; ระยะถึงศูนย์กลางเหล็กยาว/ขวาง 64/48 มม.
- ไม่พบความผิดพลาดในการอ่านหน่วย ความหนา หรือปริมาณและระดับเหล็กของข้อมูลชุดนี้
- แรงยังอ้างอิง shell midsurface; มีเพียงการหมุนแกนให้ตรงกับเหล็กและทิศผิวบน ไม่มีการย้ายจุดอ้างอิงโมเมนต์

## ผลเดิมที่รันซ้ำได้ตรง PDF

D/C เหล็กยาวล่างสูงสุด **19.734376** ที่ element **1698-5**, joint **826**, **U2A / Max**, X=19.675, Y=−2.500 ม.

| แรงที่ source เดียวกัน | ค่า | หน่วย |
|---|---:|---|
| Nx | 500.81 | kN/m |
| Ny | 203.16 | kN/m |
| Nxy | 427.96 | kN/m |
| Mx | 444.6896 | kN·m/m |
| My | 126.6933 | kN·m/m |
| Mxy | 55.9607 | kN·m/m |
| Vx | 2,920.98 | kN/m |
| Vy | 1,283.56 | kN/m |

สูตรเดิมบวก ΔTx = (Vx² + |VxVy|)/(V φv) cot29° = **7,715.892 N/mm** ให้แต่ละผิว ทั้งผิวบนและล่าง ผลสำหรับเหล็กยาวล่างที่จุดนี้จึงเป็น:

- จาก N–M เดิม: 2,340.423/(0.9×390)×1,000 = **6,667.872 มม²/ม.**
- ส่วนเพิ่มจาก V เดิม: 7,715.892/390×1,000 = **19,784.339 มม²/ม.**
- รวมที่รายงาน: **26,452.212 มม²/ม.** / As ที่มี 1,340.413 = **19.734376**

ตัวเลขประมาณ 74.8% ของ As ที่รายงานจุดนี้มาจากส่วนเพิ่ม V ที่ยังไม่ได้ตรวจยืนยันกลไก การทดสอบเดิมที่ยืนยันตัวเลขของสูตรนี้ตรวจได้เพียงว่าเขียนโปรแกรมตรงสูตร ไม่ได้ตรวจว่ากลไกเหมาะกับ shell

## ข้อบกพร่องและสิ่งที่แก้

1. **Full two-face shear addition:** สูตรคานใน AASHTO 5.7.3.5 เป็นข้อกำหนดเหล็กด้านรับแรงดึงจากดัด ไม่ใช่สิทธิให้บวกแรงเต็มจำนวนซ้ำทั้งสองผิวของ shell แบบ sandwich ทั่วไป ขณะที่สมดุลของ sandwich core/chords มีการแบ่งแรงและองค์ประกอบ xy ที่ต้องรักษาเครื่องหมาย โปรแกรมเดิมไม่ได้ตรวจ core cracking, vertical shear reinforcement หรือ interaction นั้น
2. **Angle inconsistency:** สูตรเพิ่มเหล็กเดิมใช้ θ=29° แต่ β ของ general shear screen ใช้ εs=0.006 ซึ่งให้ θ=50° ตามความสัมพันธ์เดียวกัน จึงไม่ใช่ชุดพารามิเตอร์ของ shear mechanism เดียวกัน
3. **Unqualified shear still inflated As:** แม้ที่ source ข้างต้น shear applicability ยังเป็น REVIEW โปรแกรมเดิมก็บวก ΔT เข้า As ต่อและแสดง D/C มาก การแก้แยก As ของ N–M ออกจาก V พร้อมคง REVIEW สำหรับ interaction
4. **Field selection contaminated by V:** เมื่อส่วนเพิ่ม V ครอง objective โปรแกรมเลือก a=8.750 มม. ซึ่งให้ concrete D/C=15.176 การเลือก N–M field ใหม่โดยอิสระได้ a=32.006 มม. และ concrete D/C=4.284 ที่ source เดิม ตัวเลข concrete เดิมจึงไม่ใช่หลักฐานว่าครอบคลุมการค้นหา N–M field อย่างเหมาะสม
5. **Face/core depth coupling:** การใช้ h−2a จาก N–M search เป็น dv ของ shear สามารถทำให้ผล shear ขึ้นกับวิธีเลือก face ที่เป็นคนละการตรวจ รุ่นนี้ใช้ geometric section-depth bound max[0.9(h−maximum bar-centre cover), 0.72h] สำหรับ **separate shear section screen** และระบุชัดว่าไม่ได้พิสูจน์ core reserve หรือ combined resistance

รุ่นนี้ไม่เปลี่ยนเป็นการบวกครึ่งแรงแบบอัตโนมัติ เพราะการแบ่งครึ่งอย่างเดียวไม่ได้ตรวจ cracked-core capacity, การถ่ายแรง xy และ compatibility ให้ครบ

## เปรียบเทียบผลทั้งชุด

**คอลัมน์เดิมรวมส่วนเพิ่ม V ที่ถอนออกแล้ว; คอลัมน์ใหม่เป็น N–M field เท่านั้น จึงมีขอบเขตต่างกัน** ทุกค่าคือ maximum ของแถวต้นทางจริงสำหรับเหล็กกลุ่มนั้น จุดควบคุมอาจเปลี่ยนได้

| กลุ่มเหล็ก | D/C เดิม | D/C ใหม่: N–M | As ใหม่จาก N–M (มม²/ม.) | Source ใหม่ |
|---|---:|---:|---:|---|
| Top longitudinal | 19.713805 | 4.906350 | 4,932.401 | U2A/Min · 1364-5 · joint 5 |
| Bottom longitudinal | 19.734376 | 5.188791 | 6,955.122 | U2A/Max · 1365-2 · joint 361 |
| Top transverse | 10.352446 | 1.698769 | 2,277.052 | U1A/Min · 1370-5 · joint 17 |
| Bottom transverse | 11.457093 | 2.242521 | 3,005.904 | U2A/Max · 1679-9 · joint 807 |

ที่ source เดิม 1698-5 / 826 / U2A Max: เหล็กยาวล่างเปลี่ยนจาก D/C **19.734376** เป็น **5.103710**; As ของ N–M ใหม่ = **6,841.078 มม²/ม.** การเลือก field ใหม่ทำให้ค่า N–M นี้ต่างเล็กน้อยจากส่วน N–M 6,667.872 ของ field เดิม

Peak N–M ทั้งชุด **5.188791** อยู่ X=0.325, Y=2.500 ม. ที่ 1365-2 / 361 / U2A Max พบ N–M field เกิน 1 ทั้งหมด 2,692 แถว / 460 elements ตัวเลขเหล่านี้เป็นข้อจำกัดของ finite-field preview และไม่ใช่การพิสูจน์กำลังสูงสุดของ shell ทุกกลไก

## ทำไมยังสรุปว่าผ่านไม่ได้

- Separate one-way shear screen ยังมี peak **16.351211** ที่ 1370-5 / joint 17 / U2A Min ตำแหน่ง X≈0, Y=−2.500 ม. ตัวเลขนี้เป็น **การตรวจ V แยก** ไม่ใช่เหล็กยาวล่างและไม่ใช่ combined interaction D/C
- 108,594 แถวมีผล shear screen ที่ผ่านเงื่อนไข conservative applicability; **37,838 แถว** ยังเป็น REVIEW และไม่แสดงกำลังที่ยืนยันไม่ได้
- **146,432 แถว** มี V ไม่เป็นศูนย์ จึงคง `Combined N–M–V status = REVIEW` ทั้งชุด แม้บางแถวจะผ่านการตรวจองค์ประกอบแยก
- ตัวเลข As ในตารางเป็นความต้องการของ field ที่เลือกพร้อม shrinkage minimum; concrete limit หรือ shear ที่ยังไม่ผ่านไม่สามารถแก้ได้ด้วยการคัดลอก As นี้ไปจัดเหล็กอย่างเดียว
- แรงที่มุม shell ใกล้บริเวณรองรับ/ถ่ายแรงมีค่าสูง ควรเทียบ adjacent-element values แบบไม่ average, ตรวจ mesh convergence และรวมแรงตามแถบ/หน้าตัดที่สมดุลกับ load path จริงก่อนจัดเหล็ก ไม่ควรตัด peak หรือ average ข้าม discontinuity โดยอัตโนมัติ การตรวจครั้งนี้ยังไม่ได้พิสูจน์ว่าเป็น singularity
- Anchorage, cover/exposure acceptance, flexural minimum ครบทั้งสองสาขา, fatigue, punching/local wheel effects และ SLS ยังเป็นคนละการตรวจ

## วิธีเปิดผลในรุ่นใหม่

1. เปิดโปรเจกต์ JSON เดิม แล้วนำเข้า Excel เดิมทั้งสี่ชุดใน **Loads → Slab Shell Results**
2. ไป **Analysis → Slab Reinforcement** และกด **Calculate Slab Reinforcement** หนึ่งครั้ง
3. กราฟเริ่มต้น **N–M field** แสดงค่าที่คำนวณได้ของ N–M; ตารางสี่ชั้นเหล็กใช้ขอบเขตเดียวกัน
4. เลือก **One-way shear** เพื่อดู V แยก; สีเทาคือ applicability/coverage ยังตรวจไม่ได้
5. **Overall section** แสดงค่าสูงสุดขององค์ประกอบที่ทราบ ไม่ใช่ N–M–V interaction ratio; บริเวณที่องค์ประกอบแยกผ่านแต่ interaction ยัง REVIEW จะแสดงเป็นพื้นที่ต้องตรวจทาน
6. ใช้ **What controls / All-case check breakdown** และ **Calculation trace / Equations** เพื่อตรวจ source และสมการ; CSV มี N–M, V และ combined status แยกชัด

ผลเดิมของ REVIEW57 จะไม่ถูกใช้เป็นผลปัจจุบันเมื่อเปลี่ยนรุ่น ให้ Calculate ใหม่ ข้อมูลนำเข้าและตำแหน่งเหล็กยังใช้ชุดเดิม

## การตรวจยืนยันของงานแก้ครั้งนี้

- รัน baseline57 ซ้ำตรงกับ PDF ทั้ง maxima, source identities และจำนวนแถว
- ยืนยันว่าแรงต้นทาง ความหนา และ source keys ของผลใหม่ตรงผลเดิมทุกแถว
- N–M field ของผลใหม่ตรงการแยกรัน V=0 ของ baseline ภายใน tolerance ตัวเลข (การทดสอบนี้ใช้แยกกลไก ไม่ได้แทน full interaction)
- ตรวจ force/moment equilibrium ของ governing source อย่างอิสระ; normalized six-component residual ทั้งชุดสูงสุด 1.061×10⁻¹³
- ทดสอบ regression เฉพาะส่วนที่เกี่ยวข้อง **75 tests ผ่าน** รวม physical lever arms, units, signed tensors, random equilibrium, source coverage, separate shear, review gates, stale results และ UI filters
- ทดสอบหน้าแอปจริงด้วย Streamlit AppTest: 146,432 แถว, Calculate-to-render ประมาณ 8.54 วินาทีในสภาพแวดล้อมทดสอบนี้, solver 6.66 วินาที; เปลี่ยนครบ 10 views และกรอง U2A แล้ว solver ยังคงรันเพียงหนึ่งครั้ง; หนึ่ง Plotly chart และไม่มี runtime exception
- ไม่ได้อ้างว่า AppTest เป็นการตรวจภาพ screenshot ของ browser; ไม่ได้รันทดสอบทั้ง repository หรือทำ independent structural validation ของ full N–M–V
- ขอบเขตการเปลี่ยนคือ slab N–M/V calculation/reporting; girder ULS/SLS และพฤติกรรม Project JSON ใช้ baseline เดิม ผล slab ยังคงอยู่เฉพาะ session

## แหล่งอ้างอิงที่ใช้ตรวจกลไก

1. AASHTO LRFD Bridge Design Specifications, Ninth Edition (2020), Section 5, เอกสารโครงการที่ผู้ใช้ให้: 5.7.3.4.2 และ commentary, 5.7.3.5 / C5.7.3.5, 5.5.4.2 และ 5.8.2.5.3a
2. ETH Zürich, Chair of Concrete Structures and Bridge Design, *Advanced Structural Concrete — Slabs*, 5 Dec 2023, slides 28–29: sandwich cover/core equilibrium และเงื่อนไข transverse-shear terms. แหล่งสอนกลไก ไม่ใช่มาตรฐาน AASHTO ที่นำมาแทนรหัสโครงการ: https://concrete.ethz.ch/assets/asc/autography/asc_51-slabs-part_1-as2023_auto.pdf
3. CSI, *Show Shell Force/Stress Plots*: ผลต่อหน่วยความยาวที่ midsurface และข้อสังเกตการตรวจ mesh/averaging: https://docs.csiamerica.com/help-files/csibridge/Home_tab/Display_panel/Show_Shell_Force_Stress_Plots.htm
4. CSI, *Shell Element Internal Forces/Stresses Output Convention*: https://docs.csiamerica.com/help-files/sap/Output/Shell_Element_Internal_Forces_Stresses_Output_Convention.htm

เอกสารกลไกและ numerical regression ช่วยตรวจข้อบกพร่องครั้งนี้ การยืนยันกำลัง combined N–M–V สำหรับออกแบบจริงยังต้องพัฒนาตัวแบบและตรวจยืนยันแยกตามขอบเขตนั้น
