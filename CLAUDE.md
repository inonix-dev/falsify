## Engine invariants — ห้ามละเมิดโดยไม่ถาม

engine = ฟังก์ชันบริสุทธิ์: CSV เข้า → record ออก

- ห้าม AI/LLM call, ห้าม network, ห้าม state/config file
- ห้าม tune/generate strategy — engine ต้องไม่มี stake ในผลลัพธ์
- ห้ามเพิ่ม check ใหม่จนกว่ามี user จริงขอพร้อมเคสตัวอย่าง
- ห้ามแตะ human report format เดิม (คนใช้อยู่แล้ว)
- fail-safe เข้าข้าง "ไม่รู้" มากกว่าเดาแล้วมั่นใจผิด

เหตุผลเต็ม: ROADMAP-TEMP.md · แผนปัจจุบัน: `.fapony/plan/`

<!-- code-review-graph: ถอดจาก MCP แล้ว (repo เล็ก ไม่คุ้ม context) —
     เรียกผ่าน CLI ได้เมื่อต้องการ ดู `code-review-graph --help`;
     เอากลับมาเป็น MCP ตอนเริ่ม cloud-v0 -->
