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
  // WHY: pre-commit 훅 실행 시점에는 staged 파일이 존재하므로
  //      staged 변경(XY 에서 X != ' ')은 허용하고,
  //      unstaged 변경(Y != ' ' && Y != '?') 과 untracked(??) 만 dirty 로 판정한다.
  const s = execSync('git status --porcelain').toString();
  const dirtyLines = s.split('\n').filter(line => {
    if (!line.trim()) return false;
    const xy = line.substring(0, 2);
    const isUntracked = xy === '??';
    const isUnstaged = xy[1] !== ' ' && xy[1] !== '?';
    return isUntracked || isUnstaged;
  });
  if (dirtyLines.length > 0) {
    throw new Error('작업 디렉터리 dirty: ' + dirtyLines.length + '개 변경 (unstaged/untracked)');
  }
  return 'clean (staged only)';
});

let ok = true;
for (const c of checks) {
  console.log(`${c.ok ? '✓' : '✗'} ${c.name}: ${c.msg}`);
  if (!c.ok) ok = false;
}
process.exit(ok ? 0 : 1);
