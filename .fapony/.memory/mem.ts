#!/usr/bin/env bun
// append-only memory log. ห้ามแก้บรรทัดเก่า — ปิดงาน = close (tombstone), git = ประวัติ
// log แยกต่อ app: apps/<app>/.memory/log.jsonl  → worktree ต่างกันไม่เคยแตะไฟล์เดียวกัน
//
// CLI entry point — all logic lives in:
//   store.ts       (types + config + rows/put)
//   selectors.ts   (openRows / claimsOf / staleReport)
//   render.ts      (fmtRow / fmtClose / printOpenRows / doneLines)
//   commands/write.ts  (add / close / claim / release / synced / hook)
//   commands/read.ts   (now / done / stale / find / kickoff)
//   commands/selftest.ts (test)

import {
  cmdNow,
  cmdDone,
  cmdStale,
  cmdFind,
  cmdKickoff,
} from "./commands/read.js";
import { cmdTest } from "./commands/selftest.js";
import { cmdPlanSweep, cmdPlanCheck } from "./commands/plan.js";
import { cmdRotate } from "./commands/rotate.js";
import {
  cmdAdd,
  cmdClose,
  cmdClaim,
  cmdRelease,
  cmdSynced,
  cmdHook,
} from "./commands/write.js";

const [cmd, ...a] = process.argv.slice(2);

if (cmd === "add") {
  await cmdAdd(a);
} else if (cmd === "close") {
  await cmdClose(a);
} else if (cmd === "claim") {
  cmdClaim(a);
} else if (cmd === "release") {
  await cmdRelease(a);
} else if (cmd === "synced") {
  cmdSynced(a);
} else if (cmd === "hook") {
  await cmdHook();
} else if (cmd === "done") {
  cmdDone();
} else if (cmd === "stale") {
  cmdStale();
} else if (cmd === "find") {
  cmdFind(a);
} else if (cmd === "test") {
  cmdTest();
} else if (cmd === "kickoff") {
  cmdKickoff(a);
} else if (cmd === "plan-sweep") {
  cmdPlanSweep(a);
} else if (cmd === "plan-check") {
  cmdPlanCheck(a);
} else if (cmd === "rotate") {
  cmdRotate(a);
} else {
  // mem now (default) — next+bug+hold. decision/note ไม่ใช่งานค้าง → ค้นด้วย find แทน
  cmdNow();
}
