# IGIRDER.FLEXURE31 — Final Flexure workspace

พัฒนาต่อจาก ZIP `concrete-section-pro_IGIRDER-INPUT30.zip` โดยคงสมการกำลังหน้าตัดและแรง CSI เดิม

## การใช้งาน

1. รัน `streamlit run app.py` และเปิด `I_Girder_20m_FLEXURE31_REVIEW.json`
2. ไปที่ Analysis → ULS Strength → Flexure → Final — Composite
3. เลือก Calculation scope แล้วกด **Calculate Flexure** ครั้งเดียว โปรแกรมตรวจ section flexure และ interface shear ให้พร้อมกัน
4. เลือก Girder to review, Load case และ Max/Min; ค่าเริ่มต้นแสดงหนึ่งกราฟ ส่วน Both แสดงสองกราฟเมื่อเลือกเอง
5. Result view เลือก Demand / capacity, Utilization, CSI source M3 หรือ Interface shear; View range ขยายหัว/ท้ายคานได้โดยไม่รัน solver
6. เปิด Edit composite / dowel inputs เมื่อต้องแก้ข้อมูลเดิม ไม่มีปุ่มคำนวณชุดที่สองใน Detailed workspace

เมื่อตั้ง U-dowel assessment ไว้ คำสั่งหลักจะทำ optional joint review ของ design member ด้วย ผลนี้ยังเป็นการคัดกรองกลไก ไม่เพิ่ม Girder Tn หรือยืนยัน composite V–T โดยอัตโนมัติ

## ขอบเขตหน้าตัดปลาย

- `Whole member — include cut ends`: เก็บทุกแถวไว้ในผลควบคุม
- `Span section — review cut ends separately`: แยกเฉพาะหน้าตัดปลายตัดจริง x=0/L ออกจากสรุป D/C ภายในคาน และแสดงปลายเป็น **SEPARATE REVIEW**
- JSON ที่ส่งมอบตั้งแบบแยกปลายตามคำขอ ไม่เปลี่ยนผลปลายเป็น PASS และไม่ตัดสถานีใกล้ฐานรองรับออก
- หากมีส่วนคานยื่นเลย Loads 0/L หรือพิกัดปลายจริงไม่ตรง 0/L ตัวเลือกแยกนี้จะใช้ไม่ได้ เพื่อไม่ให้ตัดหน้าตัดที่ bearing ออกจากการตรวจ
- Summary / Report ยังใช้ผลทั้งสมาชิกเดิม และแสดงสรุปช่วงคานพร้อมข้อความขอบเขตแยกต่างหาก ไม่มีการรัน solver ในสองหน้านี้

การมีเหล็กตามยาวตลอดสมาชิกไม่ยืนยันการพัฒนาแรงเต็มกำลัง ณ หน้าตัดปลายตัด ต้องพิจารณาระยะยึดเหนี่ยวและการถ่ายแรงบริเวณปลายตามรายละเอียดจริง การแยกขอบเขตการตรวจจึงไม่เท่ากับการรับรองกำลังปลายคาน

## สิ่งที่พบใน Project จริง

| สมาชิก | D/C สูงสุดของหน้าตัดภายใน ไม่รวม exact 0/L | แรงเกินกำลังภายใน | สถานะรวม |
|---|---:|---:|---|
| BOBJ1 / Interior Girder 2 | 0.460 | 0 | REVIEW |
| BOBJ1 / Left Exterior Girder | 0.488 | 0 | REVIEW |

ยังมี M2 / secondary-axis scope และ interface/dowel inputs ที่ต้องตรวจ จึงไม่เปลี่ยนสถานะรวมเป็น PASS

Left Exterior Girder มี original CSI M3 เท่ากับศูนย์ที่ 0/20 ม. ทุกกรณีที่บันทึกใน Project นี้ แต่หลังย้ายจุดอ้างอิง Mux อาจไม่เป็นศูนย์ เช่น U1A Max ที่ x=20 ม.: M3=0, CSI P=0.795 kN และ design Mux≈−0.151115 kN·m ภายใต้ reference ที่บันทึกไว้ จึงต้องแสดงสองค่าคู่กัน

Interior Girder 2 บางกรณีมี original M3 ไม่เป็นศูนย์ เช่น U1A Max ที่ x=20 ม. =1.1921 kN·m ยังต้องตรวจตำแหน่งตัด การปลดการหมุน และการถ่ายแรงในโมเดล CSI ก่อนสรุปสาเหตุ

Saved support reference สำหรับ shear ใน Project คือ x=0.400 / 19.600 ม. ซึ่งเป็นข้อมูลของแอป ไม่ใช่หลักฐานยืนยันตำแหน่ง bearing ในโมเดล CSI ปัจจุบัน

## กราฟและการตรวจสอบย้อนกลับ

- ช่องว่าง φMn เกิดเมื่อผลเดิมไม่ให้กำลังที่ใช้ได้ เช่น NO EQUILIBRIUM แสดง ×, ป้ายสถานี และแถบสีเทาโดยไม่ลากเส้นผ่านช่องว่าง
- จุดกำลังที่คำนวณได้แต่โดดเดี่ยวระหว่าง NaN แสดง marker เพื่อไม่ให้ค่าจริงหายไปเพราะ Plotly ไม่มีช่วงเส้นให้ลาก
- CSI source M3 แสดง demand ที่ origin เดิม จึงไม่วางเส้นกำลังหน้าตัดอีก origin ทับลงไป
- ตาราง End moments แสดง M3 ต้นฉบับ, P, ΔM จาก reference shift, design Mux และสถานะกำลัง แม้แถวนั้นหาสมดุลไม่ได้
- Max/Min และ Before/After ยังคงตัวตนของ source เดิม ไม่มีการหยิบอีก bound มาปิดช่องว่าง

## ขอบเขตการทดสอบ

- ชุดทดสอบที่เลือก 311 รายการผ่าน มี 7 warnings; ไม่ได้อ้างว่าทดสอบทั้ง repository
- Full app AppTest ใช้ Project จริง: section 2 ครั้ง, interface 2 ครั้ง, optional joint 1 ครั้งจากคำสั่งหลักหนึ่งครั้ง
- ผล section ทั้ง 640 แถวตรงกับ INPUT30 ทุกค่า รวม NaN และผลไม่ผ่านเดิม
- เปลี่ยนคาน/กรณีแรง/กราฟ/zoom และเปิด Summary/Report ไม่รัน solver เพิ่ม
- Raw Loads, member bank และ source origins คงเดิม
- JSON roundtrip เก็บ scope input แต่ไม่เก็บ result tables จากคำสั่ง Final Flexure ใหม่; เปิด Project อื่นล้าง view/scope widgets และ runtime ของ workspace นี้
- ทดสอบหน้าจอจริงที่ความกว้าง 1440 และ 1280 px; ภาพหน้าจอใช้ตรวจภายในและไม่รวมใน ZIP

## แหล่งอ้างอิง

- AASHTO LRFD 9th Edition (2020), Section 5 ที่ผู้ใช้ให้มา: พื้นฐานสมการเดิม ไม่ได้แก้ใน milestone นี้
- [FHWA — Variation in stress in prestressing steel along the length of girders](https://www.fhwa.dot.gov/bridge/lrfd/pscus055.cfm)
- [CSI — Show Bridge Forces / Stresses](https://docs.csiamerica.com/help-files/csibridge/Home_tab/Display_panel/Show_Bridge_Forces_Stresses.htm)
- [CSI — Introduction to CSiBridge](https://docs.csiamerica.com/manuals/csibridge/Introduction%20to%20CSiBridge.pdf): moving-load correspondence

## Repo summary

```text
IGIRDER.FLEXURE31 (base: INPUT30)
- One Final Flexure command: section + interface shear
- One selected girder / bound chart by default
- Raw CSI M3 view, labelled capacity gaps, end-reference audit
- Exact cut ends may be reported separately; no false PASS
- Inputs-only save for new Final results; read-only Summary/Report
- 311 selected tests passed; real browser QA at 1440/1280 px
```
