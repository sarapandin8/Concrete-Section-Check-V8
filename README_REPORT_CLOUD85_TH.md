# REPORT.CLOUD85 — ลด RAM และเวลาประกอบรายงาน Word ขนาดใหญ่

ต่อจาก concrete-section-pro_REPORT-EXPORT84.zip (SHA-256 26dd63e3939e7153e6f32c1c3cf81a3e116b1e5bfd685682cd2a177fe1309c33)

## ข้อค้นพบที่ทำซ้ำได้

รุ่น 84 ลดภาระการสร้างกราฟแล้ว แต่ยังประกอบเนื้อหา Word ทั้งเล่มเป็น XML object ใน RAM โดยสร้างและจัดรูปแบบใหม่ทีละ cell ตารางต้นทางจำนวนมากจึงใช้ทรัพยากรสูง แม้ DOCX ที่บีบอัดแล้วมีขนาดเล็ก

ทดสอบสร้างตารางเต็ม 15,000 แถว × 7 คอลัมน์ ใช้ข้อมูลและรูปแบบเดียวกัน ไม่ตัดแถวและไม่มีกราฟ:

| การวัด | EXPORT84 | CLOUD85 |
|---|---:|---:|
| เวลาประกอบและบันทึก Word | 66.023 s | 4.905 s |
| Peak RSS ของ Python process | 1,412.25 MiB | 127.13 MiB |
| จำนวนแถวรวม header | 15,001 | 15,001 |

เป็น benchmark บนเครื่องทดสอบ ไม่ใช่ project จริงของผู้ใช้ การอ่าน Word กลับเพื่อตรวจเนื้อหาทำแยกภายหลัง ไม่รวมเข้า peak RSS ที่รายงาน

ภาพล่าสุดยังไม่มี traceback หรือ Cloud log รอบที่ล้มเหลว จึงยังยืนยันไม่ได้ว่าเหตุการณ์ของผู้ใช้เป็น OOM หรือเกิดจากสาเหตุอื่น แต่โค้ดที่ใช้ RAM สูงข้างต้นพิสูจน์และแก้ได้แล้ว

## สิ่งที่แก้

- เขียนเนื้อหา Word ลงไฟล์ชั่วคราวทีละส่วน ปลด paragraph/table row ที่เขียนเสร็จออกจาก DOM โดยไม่ลดจำนวนแถว บท รูป หรือสมการ
- ใช้ต้นแบบแถวที่จัดรูปแบบตาม BG40 R10 แล้ว คัดลอกและใส่ค่าจริงแต่ละแถว แทนการ parse/จัดรูปแบบ cell ซ้ำทุกครั้ง
- รักษา section, styles, theme, headers, bookmarks, TOC fields, native Word equations, drawing IDs และ relationships ของแพ็กเกจเดิม
- ใช้ Kaleido 0.2.1 พร้อม flag --single-process ตาม API ที่ Plotly เผยแพร่ โดยเก็บ default flags อื่นไว้ คง batch สูงสุด 8 รูปและการปิด process group ของรุ่น 84
- แสดง progress ของบทที่กำลังเขียนจริง และรายงานความคืบหน้าตารางทุก 500 แถว พร้อม progress รายรูป
- เพิ่มเลขรุ่น REPORT.CLOUD85 ที่หน้า Calculation Report เพื่อยืนยันว่าเว็บรันโค้ดรุ่นใหม่
- บันทึกเวอร์ชัน Python/packages, ขั้นตอน, elapsed time, app RSS และ cgroup memory หากระบบเปิดเผยไว้ใน Cloud log ด้วย handler ของโมดูลโดยตรง
- หาก cgroup headroom ต่ำกว่า 96 MiB หลังเก็บ garbage แล้ว หยุด export พร้อมข้อความที่ชัดเจน เพื่อหลีกเลี่ยงการจัดสรรก้อนถัดไป guard นี้ไม่รับประกันว่าจะกัน OOM จาก native allocation ฉับพลันได้ทุกกรณี
- Pin Plotly 5.24.1 และ python-docx 1.2.0 ใช้ pandas 2.2.3 บน Python 3.12 ให้ตรงกับชุดทดสอบ ส่วน Python อื่นคง pandas>=2.2 เพื่อไม่บังคับ wheel เก่าลง Python 3.14

## รูปแบบและความครบถ้วน

ยังสร้างรายงานครบเป็นค่าเริ่มต้นด้วยการกดครั้งเดียว ไม่มี checkbox เลือกเนื้อหาเพิ่ม

เทียบตารางใหญ่และรายงาน I-girder กับ EXPORT84: document.xml หลัง canonicalization เหมือนกันทั้งหมด ได้แก่ค่าในตาราง สมการ native รูปแบบย่อหน้า/ตาราง section และตำแหน่ง/ขนาด inline images ส่วน styles, theme, headers และ package metadata ที่ไม่ใช่ภาพเหมือนกันทุก byte

CSV/JSON ใน evidence ของตัวอย่าง I-girder เทียบ 87 entries เหมือนกันทุก byte รูปใช้ Plotly traces และค่าต้นทางเดิม การรัน Chromium แบบ single-process อาจให้ anti-aliasing ของขอบตัวอักษรต่างเล็กน้อย จึงไม่ได้อ้างว่า PNG ทุกภาพเหมือนกันทุก byte ได้ตรวจ native 3D PMM export และจำนวนรูปครบด้วย

ไม่แก้สมการหรือ logic ของ engineering solvers, source acceptance gates, FAIL/REVIEW/STALE, Project JSON หรือเพิ่ม result-cache persistence หมายเลขรูปแบบเนื้อหาใน Word ยังคงเป็น REPORT.ALL82

## ผลทดสอบรายงานจริงผ่าน UI

กดปุ่ม Create ผ่าน Streamlit AppTest ใช้ native Kaleido และ exact download bytes โดยบล็อก solvers ขณะ export ผ่านครบ 7 workflow รวม 106 รูปและ 409 สมการ Word เปิดหน้าซ้ำอีก 3 ครั้งต่อ workflow โดยไม่มีการสร้างรายงานใหม่ ไม่มี process ลูกที่ยังทำงานเหลือหลังจบ

ตัวอย่าง I-girder เต็ม 58 รูปใช้ประมาณ 21 วินาทีบนเครื่องทดสอบ ตัวเลขตารางใหญ่ 4.9 วินาทีข้างต้นเป็นเฉพาะการประกอบตาราง ไม่ใช่เวลารายงานทั้งเล่ม

ผ่าน regression 208 tests (6 pandas FutureWarnings) ดูรายละเอียดและผล native UI ใน RELEASE_REPORT_CLOUD85.json และ REPORT_CLOUD85_VERIFICATION.json

เครื่องทดสอบ: Python 3.12.14 / pandas 2.2.3 / Streamlit 1.61.0 / Plotly 5.24.1 / Kaleido 0.2.1 / python-docx 1.2.0 การวัด process tree RSS รวม shared pages ซ้ำได้ ไม่ใช่ PSS/USS และไม่ใช่การวัด Cloud instance จริง

## ติดตั้งบน Streamlit Community Cloud

1. เก็บ Project JSON ต้นทาง และข้อมูล repository, branch, entrypoint, URL และ secrets ที่ต้องใช้ หากแอปหยุดไปแล้ว ผล Analysis ที่อยู่เฉพาะ session อาจต้องคำนวณใหม่
2. อัปเดตไฟล์ภายในโฟลเดอร์ concrete-section-pro ของ ZIP ให้ครบ รวม requirements.txt และไฟล์ใหม่ reporting/word_stream.py, reporting/export_runtime.py
3. แนะนำ deploy ด้วย Python 3.12 เพื่อให้ตรงกับ environment ที่ทดสอบ เอกสาร Streamlit ระบุว่า Python ของแอปเดิมเปลี่ยนด้วย Reboot ไม่ได้ หากต้องเปลี่ยนจาก 3.14 เป็น 3.12 ต้องเก็บ settings แล้ว delete/redeploy เลือก Advanced settings → Python 3.12 โดยใช้ GitHub coordinates และ custom subdomain เดิมตามคู่มือด้านล่าง ขั้นตอนนี้ผู้ดูแลแอปต้องดำเนินการเอง
4. ถ้ายังใช้ Python เดิม การอัปเดตโค้ด runtime นี้ยังทำได้ แต่ไม่มีผลทดสอบ Python 3.14 จึงไม่อ้างว่าผ่าน environment นั้นแล้ว การแก้ requirements อาจทำให้ Cloud reinstall dependencies อัตโนมัติ
5. เปิด Report / QA แล้วตรวจว่ามีข้อความ REPORT.CLOUD85 ใต้หัวข้อ Calculation Report โหลด inputs และทำ Analysis ตามขั้นตอนเดิม จากนั้นกด Create complete Word report
6. หากยังหลุด เก็บ Cloud log ของการกดครั้งนั้นจาก Manage app → เมนู ⋮ → Download log พร้อม Project JSON ที่ใช้สร้างรายงาน สิ่งที่ต้องตรวจคือบรรทัด REPORT.CLOUD85 ล่าสุด, เวอร์ชัน Python และ memory/ขั้นตอนก่อนหลุด เพื่อแยก source/model, native renderer, memory limit หรือ deployment error ไม่ควรใช้ log ก่อนเปลี่ยนรุ่นแทน

แพ็กเกจนี้ยังไม่ได้ deploy/reboot/delete live app ให้ ไม่มีการส่ง inputs ไปบริการอื่น และไม่มีการบันทึกผล Analysis ถาวรเพิ่ม

## เอกสารที่ตรวจประกอบ

- https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app
- https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app
- https://docs.streamlit.io/knowledge-base/deploy/resource-limits
- https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app/upgrade-python
- https://docs.streamlit.io/1.61.0/develop/api-reference/widgets/st.download_button
- https://discuss.streamlit.io/c/community-cloud/13
- https://github.com/plotly/Kaleido/wiki/Customizing-Chromium-Flags

เอกสาร Streamlit อธิบายว่าอาการช้า/Oh no อาจเกี่ยวกับ resource limits และให้ตรวจ Cloud logs ไม่ได้ระบุว่า Oh no ทุกกรณีคือ OOM ส่วนกระทู้ Kaleido ใน forum มีกรณีเก่าที่ทำงานบนเครื่องแต่ค้างบน Cloud จึงใช้เป็นแนวทางตรวจ ไม่ใช่หลักฐานยืนยันสาเหตุของ project นี้

## English repository summary

```text
REPORT.CLOUD85: Stream full BG40 Word tables and document content to disk,
reuse formatted row templates, reduce Chromium processes, and add Cloud
memory/stage diagnostics with tested Python 3.12 report dependency pins.
Preserve all source rows, equations, figures and engineering statuses.
```
