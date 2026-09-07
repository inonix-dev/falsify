// commands/rotate.ts — compact log.jsonl once it grows past a row-count threshold
// เก็บ open work rows + active claim ไว้ ที่เหลือ (close/release/synced ของ ref ที่ปิดแล้ว)
// git mv ไปไฟล์ archive แยก (ไม่ลบ) — ประวัติเก่ายังอยู่ ค้นย้อนหลังได้ผ่าน git log/git show

import { existsSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import { dir, LOG, rows, appendRaw } from "../store.js";
import { rotateKeep } from "../selectors.js";

// ponytail: threshold = จำนวนแถวทั้งหมด ไม่ใช่แค่ open — ที่กลัวคือไฟล์บวม/grep ช้าตอนหลายคนใช้พร้อมกัน
// (view อ่านไม่รู้เรื่องเป็นปัญหาคนละอันที่ CAP ใน write.ts จัดการอยู่แล้ว)
// 3000 กะจาก solo 1 สัปดาห์ = ~2k แถว — ปรับได้ด้วย MEM_ROTATE_THRESHOLD ถ้า pace ต่างจากนี้มาก
export const THRESHOLD = Number(process.env.MEM_ROTATE_THRESHOLD) || 3000;

export const cmdRotate = (a: string[]) => {
  const apply = a.includes("--apply");
  const all = rows();
  const over = all.length >= THRESHOLD;

  if (!apply) {
    console.log(
      `${all.length} rows (threshold ${THRESHOLD})${over ? " — เกินแล้ว, รัน --apply" : " — ยังไม่ถึง"}`,
    );
    return;
  }
  if (!over && !process.env.MEM_FORCE) {
    console.log(
      `${all.length}/${THRESHOLD} rows — ยังไม่ถึง threshold ไม่ต้อง rotate (MEM_FORCE=1 ถ้าอยากทำเลย)`,
    );
    return;
  }

  const keep = rotateKeep(all);
  const stamp = new Date().toISOString().slice(0, 10);
  const archived = join(dir, `log.${stamp}.jsonl`);
  if (existsSync(archived)) {
    console.error(
      `${archived} มีอยู่แล้ว (rotate ไปแล้ววันนี้?) — ลบ/ย้ายไฟล์เก่าก่อนถ้าอยากรันซ้ำ`,
    );
    process.exit(1);
  }

  // เหมือน plan-sweep: stage ก่อนกัน git mv fail เงียบถ้าไฟล์ยังไม่ track (exit 128)
  Bun.spawnSync(["git", "add", LOG]);
  const mv = Bun.spawnSync(["git", "mv", LOG, archived]);
  if (mv.exitCode !== 0) {
    console.error(
      `git mv ล้มเหลว (${mv.stderr.toString().trim()}) — rotate ไม่สำเร็จ`,
    );
    process.exit(1);
  }

  writeFileSync(LOG, "");
  for (const r of keep) appendRaw(LOG, r);

  console.log(
    `rotated: ${all.length} rows → archive ${archived.replace(dir + "/", "")} (git history อยู่ครบ), เหลือ ${keep.length} แถว (open + active claim) ใน log.jsonl`,
  );
};
