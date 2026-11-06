import { execFileSync } from "node:child_process";
import { resolve } from "node:path";

export default function teardown() {
  execFileSync(resolve("backend/.venv/Scripts/python.exe"), ["-m", "scripts.admin_browser_fixture", "cleanup"], {
    cwd: resolve("backend"), stdio: "pipe", windowsHide: true,
  });
}
