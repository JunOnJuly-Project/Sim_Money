#!/usr/bin/env node
// 환경 점검 스크립트 — 크로스 플랫폼 (Windows/Linux/macOS)
// 사용: node scripts/env-check.js
const { execSync } = require('child_process');
const fs = require('fs');

const checks = [];
function check(name, fn) {
  try { checks.push({ name, ok: true, msg: fn() }); }
  catch (e) { checks.push({ name, ok: false, msg: e.message }); }
}

check('Git', () => execSync('git --version').toString().trim());
check('Node', () => process.version);
check('.env 존재', () => fs.existsSync('.env') ? 'OK' : (() => { throw new Error('.env.example 를 복사하여 .env 생성 필요'); })());
check('HANDOFF.md 존재', () => fs.existsSync('HANDOFF.md') ? 'OK' : (() => { throw new Error('/handoff init 실행 필요'); })());
check('git clean', () => {
  const s = execSync('git status --porcelain').toString();
  if (s.trim()) throw new Error('작업 디렉터리 dirty: ' + s.split('\n').length + '개 변경');
  return 'clean';
});

let ok = true;
for (const c of checks) {
  console.log(`${c.ok ? '✓' : '✗'} ${c.name}: ${c.msg}`);
  if (!c.ok) ok = false;
}
process.exit(ok ? 0 : 1);
