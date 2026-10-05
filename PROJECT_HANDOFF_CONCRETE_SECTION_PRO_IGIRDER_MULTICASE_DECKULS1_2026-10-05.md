# IGIRDER.MULTICASE1 / DECKULS1 — handoff and use guide

Date: 2026-10-05. Authoritative baseline: IGIRDER.SHEARCOMP1 final-composite-bearing400. All baseline Python files matched the accepted ZIP before modification. This release extends Concrete Section Pro, not the separate Segmental Box Girder application.

## สิ่งที่แก้แล้ว

| รายการ | พฤติกรรมรุ่นนี้ |
|---|---|
| นำเข้า ULS หลายตาราง | Upload หลาย XLSX/CSV พร้อมกัน เลือก worksheet รายไฟล์ และ Replace/Append เป็นชุดเดียวได้ ต้องเป็น girder ตัวเดียวและจุดเริ่ม station เดียวกัน |
| ที่มาของแรง | เก็บไฟล์/worksheet/OutputCase/StepType/StepNum/controlling response (เมื่อมี)/แถว/ชุดซ้ำใน Note ทั้ง 6 องค์ประกอบยังอยู่ใน vector เดิม ไม่สร้าง component envelope ผสมใหม่ |
| Concurrency | เลือก Envelope/unverified, Static combination/explicit step หรือ CSI Correspondence พร้อม declaration และ source basis. Max/Min ภายใต้ Static ยังเป็น ENVELOPE. Declaration เป็นข้อมูลจากผู้ออกแบบ ไม่ใช่การตรวจไฟล์ CSI model โดยอัตโนมัติ |
| เหล็ก deck | บน–ล่าง: diameter, spacing, cover, grade/fy แยกชั้น, Es, cutoff start/end, continuity, verified ld หรือ conservative Auto, end anchorage แยกชั้น |
| Final Flexure | สร้าง composite polygon เดิมร่วมเหล็กตามยาว deck ตาม As=Ab Be/s ที่ตำแหน่งจริง; ตรวจทั้งเครื่องหมายบวกและลบ. Negative acceptance ต้องมีชั้น deck ที่นิยามและยืนยัน พร้อม station development และ gates อื่น |
| Final Shear + Torsion | เหล็ก deck ที่ยืนยันแล้วเข้าสมดุล C/T, de/dv, strain stiffness และแรง As fy บน tension half จริง. ไม่ใช้ girder anchorage ไปให้เครดิต deck |
| Development | ใช้เส้นผ่านศูนย์กลาง bar จริงหา ld ไม่ใช่ equivalent diameter ของทั้ง layer; ใช้กำลัง deck concrete และ ld ขั้นต่ำ 304.8 mm. Bar cutoff ไม่เลื่อนตาม bearing |
| Below-minimum General Procedure | มี ag และ optional reduced sx พร้อม verification; sxe=sx*1.38/(ag[in]+0.63), clamp 12–80 in. ให้ numerical Eq.-2 audit ได้ แต่ minimum/spacing detailing ยัง FAIL ตามจริง |
| แสดงผล | Section basis, composite gate, source coupling, h/dv และ support region อยู่ใกล้ด้านซ้าย/ตารางสรุป. คำอธิบายคงที่ไม่อ้าง verified composite อีก |
| Bearing | แยก region/overhang review พร้อมเหตุผล โดยไม่ลบ source rows ไม่เปลี่ยน FAIL และไม่ย้าย strand cut ends. Region flag ไม่ใช่คำตอบ STM |
| JSON/cache | เก็บ input parameters/source tags; ล้าง deck-widget transport ก่อนเปิดโครงการอื่น. เปลี่ยนรุ่น/inputs ทำให้ Final strength results เดิม stale. ไม่มี persistent solver cache เพิ่ม |
| กราฟเดิม | รับ source tag CSIIMPORT2 เก่าและรุ่นใหม่; endpoint sharing ไม่ข้าม source file, step number หรือ controlling response |

## วิธีใช้

1. Loads: เลือก kN และ kN-m → Upload หลายไฟล์. เลือก Girder worksheet เดียวกันทุกไฟล์. ค่าที่นำเข้าต้องเป็น **factored ULS combination/analysis result** แล้ว; แอปไม่ได้ใส่ load factor ให้ DEAD/LL ที่ยังไม่ factored.
2. ยืนยัน same member/station origin และ raw CSI P sign. P บวก = tension, ลบ = compression; solver แปลงตามระบบเดิม. ไม่ตั้ง P=0 ให้เอง.
3. ระบุ Force-vector source รายไฟล์. Static ต้องเป็น combination หรือ explicit step ที่ simultaneous จริง; moving-load envelope ยังต้องใช้ Correspondence. หากยังไม่ยืนยัน ให้เก็บ Envelope/REVIEW.
4. Sections → Composite Deck Longitudinal Reinforcement: เลือก Include และกรอกเหล็กบน–ล่าง/เกรด/cover/ระยะพัฒนาแรงตามแบบ. โครงการเก่าคง include/exclude ที่เคย save; ต้องเปิด Include หากต้องการนำเหล็ก deck มาคิด. ไม่มีการเดาขนาดเหล็กให้โครงการจริง.
5. ตรวจ Be และทำ Interface Shear ให้ได้ current PASS. กด Calculate Final Composite Flexure และ Calculate Shear + Torsion ใหม่.
6. ดู Section basis และ Source coupling แยกจาก Composite action status/Depth source status. CONCURRENT — DECLARED หมายถึงมีฐานข้อมูลตาม declaration ไม่ใช่แอปเปิดตรวจ CSI model แล้ว.
7. Save Project JSON เพื่อเก็บ inputs/ที่มาชุดแรง. เปิด JSON แล้วคำนวณผลใหม่ตาม workflow เดิม.

## ขอบเขตที่ยังต้องตรวจแยก — ไม่เรียกรุ่นนี้ว่าออกแบบสะพานครบทุกเรื่อง

| รายการ | ขอบเขตปัจจุบัน / ข้อมูลที่ต้องมีเพื่อพัฒนาหรือออกแบบต่อ |
|---|---|
| Composite torsion โดยให้ deck ร่วมรับ | Ao/ph และ hoop resistance ยังจาก closed girder hoop จริง. ยังไม่มี composite torsional force-flow/connection model. ต้องมีแนว closed shear-flow, reinforcement layout, interface connection และ load path ก่อนให้เครดิต deck เป็น torsional tube |
| Bearing/end D-region/STM | ทราบ bearing CL x=0.4/19.6 m; ยังไม่มี footprint/reaction/end details ของโครงการครบ. แอประบุ region review แต่ไม่ได้แก้ STM/nodal strength, local bearing, splitting/confinement, overhang load path. ต้องมี bearing size, reactions พร้อม load case และแบบเหล็กปลายคาน |
| Deck transverse design | เหล็กขวางไม่ถูกนับเป็นเหล็กตามยาวหรือ hoop ของ girder. Slab transverse flexure/shear และ detailing ยังเป็นการตรวจแยก |
| Development execution | Conservative straight-bar source และ verified end declaration ไม่ใช่การตรวจตะขอ/lap splice/ทุก cutoff ตาม shop drawing โดยอัตโนมัติ |
| Biaxial / fatigue | เก็บ M2/V3 เป็น reference ตามเดิม ไม่ใช่ combined biaxial หรือ fatigue module |
| Negative combined pretensioned route | มี deck tension contribution จริงแล้ว แต่ข้อกำหนด prestress dominance ของ route เดิมยังอาจ FAIL เมื่อ top-side Aps ไม่มี. ไม่ทำให้ PASS ด้วยการเพิ่ม ordinary deck bars หรือยกเลิก gate เงียบ ๆ. Alternative RC continuity route ไม่ได้ implement ใน release นี้ |

**Sectional PASS ต้องอ่านภายในขอบเขตนี้. ไม่ใช่ PASS สำหรับ bearing/D-region, torsional deck force-flow หรือการออกแบบสะพานทั้งระบบ.**

## Engineering basis and implementation

Primary reference: user-supplied AASHTO LRFD 9th (2020) Section 5, especially 5.6.2.1 / 5.6.3.2.6; 5.7.2.8; 5.7.3.4.2; 5.7.3.5; 5.7.3.6; 5.9.4.3; 5.10.8.2.1. The conservative uniform lower deck/girder concrete strength approximation is retained; web fc and bv remain precast. This is the AASHTO bridge route, not a conversion to ACI.

CSI primary documentation: [Load Combination Data](https://docs.csiamerica.com/help-files/csibridge/Design_Rating_tab/Load_Combinations/Load_Combination_Data_Form.htm) and [Modeling Process / Correspondence](https://docs.csiamerica.com/help-files/csibridge/Getting_Started/Modeling_Process.htm). A separately uploaded moving-load envelope does not become a simultaneous vector automatically.

Changed areas: io/girder_csi_import.py; ui/girder_csi_import.py; analysis/igird_composite_flexure.py; analysis/igird_deck_development.py (new); analysis/igird_flexure_development.py; analysis/igird_shear_depth.py; analysis/igird_crack_spacing.py (new); analysis/igird_shear_support.py; ui/section_builder.py; ui/igird_shear_section.py; ui/igird_combined_vt.py; ui/igird_vt_workspace.py; ui/analysis_page.py; visualization/igird_uls_chart_display.py; io/project_io.py.

Regression test assertions updated only for the intentional UI label and cache-version changes. Previous numerical assertions are retained. Construction remains precast; deck inputs live in Final composite preparation. Generic solver equations, load factors, original source values, and result persistence behavior were not replaced. Imported CSI data is never converted to zero axial force.

Validation and package identity are recorded below after the final clean-package checks.

Repo summary: Add multi-table ULS force-vector provenance and station-developed deck reinforcement to Final-composite resistance, with explicit source and engineering scope gates.
