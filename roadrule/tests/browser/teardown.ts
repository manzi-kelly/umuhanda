import { execFileSync } from "node:child_process";
import { resolve } from "node:path";

export default function teardown() {
  execFileSync(
    resolve("backend/.venv/Scripts/python.exe"),
    ["-m", "scripts.admin_browser_fixture", "cleanup"],
    {
      cwd: resolve("backend"),
      env: { ...process.env, PHASE04D_BROWSER_ACCESS: "1" },
      windowsHide: true,
    },
  );
}
