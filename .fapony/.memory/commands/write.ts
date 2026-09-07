// commands/write.ts — mutating commands: add, close, claim, release, synced, hook

import type { WorkKind } from "../store.js";

import { openRows, claimsOf } from "../selectors.js";
import { root, KINDS, rows, put, nextId } from "../store.js";

export const cmdAdd = async (a: string[]) => {
  // mem add <next|bug|decision|note|hold> "<text>" [path/to/SPEC.md]
  // mem add <kind> --stdin [spec.md]   ← read text from stdin (avoids shell metachar issues)
  // ponytail: kind ผิด = แถวนั้นหายจาก view เงียบๆ — ตายตั้งแต่ตรงนี้ดีกว่า
  if (!KINDS.includes(a[0] as WorkKind)) {
    console.error(`kind ต้องเป็น ${KINDS.join("|")} — ได้ "${a[0] ?? ""}"`);
    process.exit(1);
  }
  // hold บังคับ spec
  if (a[0] === "hold" && !a.at(-1)?.endsWith(".md")) {
    console.error(
      `hold บังคับ spec — ใช้: bun .memory/mem.ts add hold "..." <spec.md>`,
    );
    process.exit(1);
  }
  const arg = a.slice(1);
  const useStdin = arg.includes("--stdin");
  const filtered = arg.filter((x) => x !== "--stdin");
  const spec = filtered.at(-1)?.endsWith(".md") ? filtered.pop() : undefined;
  let text: string;
  if (useStdin) {
    text = (await Bun.stdin.text()).trim();
    if (!text) {
      console.error("stdin ว่าง — ต้องมีข้อความ");
      process.exit(1);
    }
  } else {
    // ต้องมีข้อความ
    if (!filtered.length || (filtered.length === 0 && !spec)) {
      console.error(
        'ต้องมีข้อความ — ใช้: bun .memory/mem.ts add <kind> "<text>" [spec.md]',
      );
      process.exit(1);
    }
    text = filtered.join(" ");
  }
  // read once — cap check + id collision
  const all = rows();
  // ponytail: เพดาน open next/hold กันสะสมไม่มีที่สิ้นสุด — บังคับ triage ของเก่าก่อนเปิดใหม่
  const CAP = 15;
  const CAP_HOLD = 10;
  if (a[0] === "next" && !process.env.MEM_FORCE) {
    const openNext = openRows(all).filter((r) => r.kind === "next").length;
    if (openNext >= CAP) {
      console.error(
        `open next ${openNext}/${CAP} เต็มแล้ว — close ของเก่าก่อน (หรือ MEM_FORCE=1 ถ้าจำเป็นจริงๆ)`,
      );
      process.exit(1);
    }
  }
  if (a[0] === "hold" && !process.env.MEM_FORCE) {
    const openHold = openRows(all).filter((r) => r.kind === "hold").length;
    if (openHold >= CAP_HOLD) {
      console.error(
        `open hold ${openHold}/${CAP_HOLD} เต็มแล้ว — close/release ของเก่าก่อน (หรือ MEM_FORCE=1)`,
      );
      process.exit(1);
    }
  }
  // ponytail: กัน id ชน — logic รวมไว้ที่ nextId (store.ts)
  const id = nextId(all);
  put({ id, kind: a[0] as WorkKind, text, spec });
  console.log(id);
};

export const cmdClose = async (a: string[]) => {
  // mem close <id> "<ทำอะไร / commit>" — tombstone ทำให้ claim void เอง
  // mem close <id> --stdin ← read text from stdin
  if (!a[0]) {
    console.error(
      'ต้องระบุ id — ใช้: bun .memory/mem.ts close <id> "<ข้อความ>"',
    );
    process.exit(1);
  }
  if (!rows().some((r) => "id" in r && r.id === a[0])) {
    console.error(`ไม่มี id "${a[0]}" ใน log`);
    process.exit(1);
  }
  const rest = a.slice(1);
  const useStdin = rest.includes("--stdin");
  let text: string;
  if (useStdin) {
    text = (await Bun.stdin.text()).trim();
  } else {
    text = rest.join(" ");
  }
  put({ kind: "close", ref: a[0], text });
};

export const cmdClaim = (a: string[]) => {
  // mem claim <id> — ต้องมี id จริง, open, kind=next|bug, ไม่มี active claim ค้าง
  if (!a[0]) {
    console.error("ต้องระบุ id — ใช้: bun .memory/mem.ts claim <id>");
    process.exit(1);
  }
  const all = rows();
  const open = openRows(all);
  const target = open.find((r) => r.id === a[0]);
  if (!target) {
    const exists = all.find((r) => "id" in r && r.id === a[0]);
    console.error(
      exists
        ? `id "${a[0]}" มีอยู่แต่ปิดไปแล้ว (close tombstone)`
        : `ไม่มี id "${a[0]}" ใน log`,
    );
    process.exit(1);
  }
  if (target.kind !== "next" && target.kind !== "bug") {
    console.error(`claim ได้เฉพาะ next/bug — id "${a[0]}" เป็น ${target.kind}`);
    process.exit(1);
  }
  const claims = claimsOf(all);
  if (claims.has(a[0])) {
    const c = claims.get(a[0])!;
    console.error(`id "${a[0]}" ถูก claim โดย ${c.agent} แล้ว — release ก่อน`);
    process.exit(1);
  }
  put({ kind: "claim", ref: a[0] });
  console.log(`claimed ${a[0]}`);
};

export const cmdRelease = async (a: string[]) => {
  // mem release <id> "<เหตุผล>?"
  // mem release <id> --stdin ← read text from stdin
  if (!a[0]) {
    console.error(
      "ต้องระบุ id — ใช้: bun .memory/mem.ts release <id> [เหตุผล]",
    );
    process.exit(1);
  }
  const all = rows();
  const claims = claimsOf(all);
  if (!claims.has(a[0])) {
    console.error(`id "${a[0]}" ไม่มี active claim`);
    process.exit(1);
  }
  const rest = a.slice(1);
  const useStdin = rest.includes("--stdin");
  let text: string | undefined;
  if (useStdin) {
    const t = (await Bun.stdin.text()).trim();
    text = t || undefined;
  } else {
    text = rest.join(" ") || undefined;
  }
  put({ kind: "release", ref: a[0], text });
  console.log(`released ${a[0]}`);
};

export const cmdSynced = (a: string[]) => {
  // mem synced [path.md ...] — ประกาศว่า spec ตรงกับ log แล้ว (ไม่ระบุ = ทุก spec ที่ log อ้างถึง)
  const specs = a.length
    ? a
    : [
        ...new Set(
          rows()
            .filter((r) => r.kind === "synced" || ("spec" in r && r.spec))
            .map((r) => ("spec" in r ? r.spec : undefined))
            .filter(Boolean) as string[],
        ),
      ];
  for (const spec of specs) put({ kind: "synced", spec });
  console.log(`synced ${specs.length} spec`);
};

export const cmdHook = async () => {
  // PostToolUse: stdin = {tool_input:{file_path}} → แก้ spec ของ app นี้เสร็จ = synced ให้เอง
  const j = (await Bun.stdin.json().catch(() => null)) as Record<
    string,
    unknown
  > | null;
  const f =
    j && typeof j === "object" && "tool_input" in j
      ? ((j as { tool_input?: { file_path?: string } }).tool_input?.file_path ??
        "")
      : "";
  const { app } = await import("../store.js");
  const rel = f.startsWith(root) ? f.slice(root.length + 1) : f;
  if (new RegExp(`^apps/${app}/(plan/(done/)?)?PLAN.*\\.md$`).test(rel)) {
    put({ kind: "synced", spec: rel });
    console.log(`synced ${rel}`);
  }
};
