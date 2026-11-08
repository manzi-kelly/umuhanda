import { test } from "node:test";
import { createRequire } from "node:module";
import assert from "node:assert/strict";
import fs from "node:fs";
import ts from "typescript";

// Compile the pure TypeScript proxy module with the installed compiler.
const load = createRequire(import.meta.url);
load.extensions[".ts"] = (module, filename) => {
  const source = fs.readFileSync(filename, "utf8");
  module._compile(
    ts.transpileModule(source, {
      compilerOptions: {
        module: ts.ModuleKind.CommonJS,
        target: ts.ScriptTarget.ES2020,
      },
      fileName: filename,
    }).outputText,
    filename,
  );
};

const { studentProxyConfig, studentRequestAllowed, studentUpstreamUrl } = load(
  "../src/features/onboarding/proxy.ts",
);

test("production bridge uses the existing NEXT_PUBLIC_API_URL and maps to /api/v1", () => {
  const config = studentProxyConfig({
    NODE_ENV: "production",
    NEXT_PUBLIC_API_URL: "https://umuhanda-production.up.railway.app",
  });
  assert.deepEqual(config, {
    frontend: "https://umuhanda.vercel.app",
    api: "https://umuhanda-production.up.railway.app",
    secure: true,
    backendCookie: "__Secure-roadrules_guest",
    browserCookie: "__Secure-roadrules_student_ui",
  });
  assert.equal(
    studentUpstreamUrl(config.api, "students/sessions").href,
    "https://umuhanda-production.up.railway.app/api/v1/students/sessions",
  );
});

test("versioned and trailing-slash API values do not duplicate the prefix", () => {
  for (const value of [
    "https://umuhanda-production.up.railway.app/",
    "https://umuhanda-production.up.railway.app/api/v1",
    "https://umuhanda-production.up.railway.app/api/v1/",
  ]) {
    const config = studentProxyConfig({
      NODE_ENV: "production",
      NEXT_PUBLIC_API_URL: value,
    });
    assert.equal(config.api, "https://umuhanda-production.up.railway.app");
    assert.equal(
      studentUpstreamUrl(config.api, "exams/me").href,
      "https://umuhanda-production.up.railway.app/api/v1/exams/me",
    );
  }
});

test("server-only overrides take precedence over public and admin names", () => {
  const config = studentProxyConfig({
    NODE_ENV: "production",
    NEXT_PUBLIC_API_URL: "https://public.example",
    ADMIN_API_ORIGIN: "https://admin.example",
    STUDENT_API_ORIGIN: "https://student.example",
    ADMIN_FRONTEND_ORIGIN: "https://admin-frontend.example",
    STUDENT_FRONTEND_ORIGIN: "https://student-frontend.example",
  });
  assert.equal(config.api, "https://student.example");
  assert.equal(config.frontend, "https://student-frontend.example");
});

test("local loopback bridge preserves the development cookie names", () => {
  const config = studentProxyConfig({
    NODE_ENV: "production",
    ADMIN_LOCAL_DEVELOPMENT: "1",
    ADMIN_API_ORIGIN: "http://127.0.0.1:8310",
    ADMIN_FRONTEND_ORIGIN: "http://127.0.0.1:3100",
  });
  assert.equal(config.api, "http://127.0.0.1:8310");
  assert.equal(config.frontend, "http://127.0.0.1:3100");
  assert.equal(config.secure, false);
  assert.equal(config.backendCookie, "roadrules_guest");
  assert.equal(config.browserCookie, "roadrules_student_ui");

  assert.deepEqual(
    studentProxyConfig({ NODE_ENV: "development" }),
    {
      frontend: "http://localhost:3000",
      api: "http://127.0.0.1:8000",
      secure: false,
      backendCookie: "roadrules_guest",
      browserCookie: "roadrules_student_ui",
    },
  );
});

test("production rejects missing, insecure, credentialed and pathful origins", () => {
  assert.throws(
    () => studentProxyConfig({ NODE_ENV: "production" }),
    /not configured/,
  );
  assert.throws(
    () =>
      studentProxyConfig({
        NODE_ENV: "production",
        NEXT_PUBLIC_API_URL: "http://umuhanda-production.up.railway.app",
      }),
    /require HTTPS/,
  );
  for (const value of [
    "https://user:pass@umuhanda-production.up.railway.app",
    "https://umuhanda-production.up.railway.app/api/v1/students",
    "https://umuhanda-production.up.railway.app?next=https://evil.example",
  ]) {
    assert.throws(
      () =>
        studentProxyConfig({
          NODE_ENV: "production",
          NEXT_PUBLIC_API_URL: value,
        }),
      /Invalid student API origin/,
      value,
    );
  }
  assert.throws(
    () =>
      studentProxyConfig({
        NODE_ENV: "production",
        NEXT_PUBLIC_API_URL: "https://umuhanda-production.up.railway.app",
        STUDENT_FRONTEND_ORIGIN: "http://umuhanda.vercel.app",
      }),
    /require HTTPS/,
  );
});

test("local mode refuses non-loopback origins", () => {
  assert.throws(
    () =>
      studentProxyConfig({
        NODE_ENV: "development",
        ADMIN_API_ORIGIN: "https://umuhanda-production.up.railway.app",
        ADMIN_FRONTEND_ORIGIN: "http://localhost:3000",
      }),
    /loopback/,
  );
});

test("request policy keeps the existing student API allowlist", () => {
  const id = "00000000-0000-4000-8000-000000000000";
  for (const [method, path] of [
    ["POST", "students/sessions"],
    ["POST", "payments/mock/initiate"],
    ["POST", "promos/redeem"],
    ["POST", "exams/start"],
    ["POST", `exams/${id}/next`],
    ["PUT", `exams/${id}/answer`],
    ["GET", "exam-access/me"],
    ["GET", "exams/me"],
    ["GET", `exams/${id}/current`],
    ["GET", `exams/${id}/result`],
    ["GET", `exams/${id}/media/1/2`],
    ["GET", "students/exams/history"],
    ["GET", `payments/${id}/status`],
  ]) {
    assert.equal(studentRequestAllowed(method, path), true, `${method} ${path}`);
  }
  for (const [method, path] of [
    ["POST", "students/sessions/revoke"],
    ["POST", "admin/auth/login"],
    ["PUT", `exams/${id}/result`],
    ["DELETE", `exams/${id}`],
    ["GET", "admin/dashboard/summary"],
    ["GET", "students/sessions"],
    ["GET", "../admin"],
  ]) {
    assert.equal(
      studentRequestAllowed(method, path),
      false,
      `${method} ${path}`,
    );
  }
});

test("no Vercel edge rewrite shadows the secure student bridge", () => {
  assert.equal(load("../next.config.ts").default.rewrites, undefined);
  const vercel = new URL("../vercel.json", import.meta.url);
  if (fs.existsSync(vercel)) {
    const config = JSON.parse(fs.readFileSync(vercel, "utf8"));
    assert.equal(config.rewrites?.length ?? 0, 0);
    assert.equal(config.routes?.length ?? 0, 0);
  }

  const route = fs.readFileSync(
    new URL("../src/app/student-api/[...path]/route.ts", import.meta.url),
    "utf8",
  );
  assert.match(route, /studentProxyConfig\(\)/);
  assert.match(route, /studentUpstreamUrl\(config\.api, path, query\)/);
});
