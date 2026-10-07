const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');

const script = path.join(__dirname, 'passport_package_check.js');
const sha = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex').toUpperCase();
const contract = path.join(__dirname, '..', '00A_Контракт_передач_Паспорта_SKU.md');
const contractVersion = fs.readFileSync(contract, 'utf8').match(/^Версия:\s*([^\s]+)/m)[1];
function writeStoredDocx(file, text) {
  const name = Buffer.from('word/document.xml');
  const data = Buffer.from(`<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="x"><w:body><w:p><w:r><w:t>${text}</w:t></w:r></w:p></w:body></w:document>`);
  const local = Buffer.alloc(30);
  local.writeUInt32LE(0x04034b50, 0); local.writeUInt16LE(20, 4); local.writeUInt32LE(data.length, 18); local.writeUInt32LE(data.length, 22); local.writeUInt16LE(name.length, 26);
  const central = Buffer.alloc(46);
  central.writeUInt32LE(0x02014b50, 0); central.writeUInt16LE(20, 4); central.writeUInt16LE(20, 6); central.writeUInt32LE(data.length, 20); central.writeUInt32LE(data.length, 24); central.writeUInt16LE(name.length, 28);
  const eocd = Buffer.alloc(22);
  eocd.writeUInt32LE(0x06054b50, 0); eocd.writeUInt16LE(1, 8); eocd.writeUInt16LE(1, 10); eocd.writeUInt32LE(central.length + name.length, 12); eocd.writeUInt32LE(local.length + name.length + data.length, 16);
  fs.writeFileSync(file, Buffer.concat([local, name, data, central, name, eocd]));
}
function fixture(format = 'md', docxText = 'Паспорт SKU — TEST NOT_READY') {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'passport-check-test-'));
  const run = path.join(root, 'COLLECTOR-RUN-TEST');
  fs.mkdirSync(run);
  const passport = path.join(root, `Паспорт_SKU__TEST.${format}`);
  if (format === 'docx') writeStoredDocx(passport, docxText);
  else fs.writeFileSync(passport, '# Паспорт SKU — TEST\nstate=NOT_READY\n');
  const roles = ['source_manifest', 'candidate_update', 'collector_handoff', 'change_events'];
  const files = Object.fromEntries(roles.map(role => {
    const file = path.join(run, `${role}__TEST__RUN.md`);
    fs.writeFileSync(file, `# ${role}\n`);
    return [role, file];
  }));
  const preflight = path.join(run, 'preflight_report__TEST__RUN.md');
  fs.writeFileSync(preflight, '| check_id | result |\n|---|---|\n| PF-STATE-RECONCILIATION | PASS |\n| PF-EVIDENCE-REPRODUCIBILITY | PASS |\n| PF-HANDOFF-COMPLETENESS | PASS |\n');
  const manifest = path.join(run, 'package_manifest__TEST__RUN.md');
  const rows = roles.map(role => `| ${role} | ${files[role]} | ${fs.statSync(files[role]).size} | ${sha(files[role])} | now |`);
  fs.writeFileSync(manifest, `# Package manifest\npackage_admissible_for_audit=true\npassport_id=TEST\npassport_sha256=${sha(passport)}\ncontract_version=${contractVersion}\ncontract_sha256=${sha(contract)}\n| file_role | exact_path | size_bytes | SHA-256 | created_at |\n|---|---|---:|---|---|\n${rows.join('\n')}\n`);
  const profile = path.join(root, 'CATEGORY_PROFILE_APPROVAL.json');
  fs.writeFileSync(profile, JSON.stringify({ profile_version: '1.0', field_count: 22 }));
  return { root, run, passport, profile, files, manifest };
}
function check(f, extra = []) {
  const out = spawnSync(process.execPath, [script, '--product-root', f.root, '--run-dir', f.run, '--passport', f.passport, '--profile-approval', f.profile, '--stage', 'auditor', ...extra], { encoding: 'utf8' });
  return { status: out.status, result: JSON.parse(out.stdout) };
}
function cleanup(f) {
  const temp = fs.realpathSync(os.tmpdir());
  const actual = fs.realpathSync(f.root);
  assert.ok(actual.startsWith(temp + path.sep) && path.basename(actual).startsWith('passport-check-test-'));
  fs.rmSync(actual, { recursive: true, force: true });
}
test('accepts complete structural fixture', () => {
  const f = fixture();
  try { const x = check(f); assert.equal(x.status, 0); assert.equal(x.result.status, 'PASS'); }
  finally { cleanup(f); }
});
test('rejects stale request for an approved category profile', () => {
  const f = fixture();
  try {
    fs.appendFileSync(f.files.candidate_update, '| GAP-004 | high | validated category field profile absent | OPEN |\n');
    const x = check(f);
    assert.equal(x.result.status, 'FAIL');
    assert.ok(x.result.findings.some(v => v.code === 'STALE_PROFILE_REQUEST'));
    assert.ok(x.result.diagnostics.some(v => v.code === 'MANIFEST_HASH_MISMATCH'));
  } finally { cleanup(f); }
});
test('rejects an unapproved passport projection document', () => {
  const f = fixture();
  try {
    fs.writeFileSync(path.join(f.run, 'Робоча_проекція_Паспорта.md'), '# Projection\n');
    const x = check(f);
    assert.ok(x.result.findings.some(v => v.code === 'UNAPPROVED_PASSPORT_DOCUMENT'));
  } finally { cleanup(f); }
});
test('accepts DOCX Passport and ignores passport section matrix', () => {
  const f = fixture('docx');
  try {
    fs.writeFileSync(path.join(f.run, 'passport_section_matrix__TEST__RUN.md'), '# Support matrix\n');
    const x = check(f);
    assert.equal(x.result.status, 'PASS');
    assert.equal(x.result.diagnostics.length, 0);
  } finally { cleanup(f); }
});
test('rejects readable DOCX Passport without an allowed state', () => {
  const f = fixture('docx', 'Паспорт SKU — TEST');
  try {
    const x = check(f);
    assert.equal(x.result.status, 'FAIL');
    assert.ok(x.result.findings.some(v => v.code === 'PASSPORT_STATE_MISSING'));
  } finally { cleanup(f); }
});
test('verifier requires an accepted audit for the exact collector package', () => {
  const f = fixture();
  try {
    const audit = path.join(f.root, 'audit_report.md');
    fs.writeFileSync(audit, `handoff_scope=FULL_PASSPORT\nhandoff_verdict=READY_FOR_VERIFIER\ninput_receipt=ACCEPTED\ncollector_package_sha256=${sha(f.manifest)}\n`);
    const accepted = spawnSync(process.execPath, [script, '--product-root', f.root, '--run-dir', f.run, '--passport', f.passport, '--stage', 'verifier', '--audit-report', audit], { encoding: 'utf8' });
    assert.equal(JSON.parse(accepted.stdout).status, 'PASS');
    fs.writeFileSync(audit, `handoff_scope=LIMITED_EXTRACTION_AUDIT\nhandoff_verdict=READY_FOR_VERIFIER\ninput_receipt=ACCEPTED\ncollector_package_sha256=${sha(f.manifest)}\n`);
    const scoped = spawnSync(process.execPath, [script, '--product-root', f.root, '--run-dir', f.run, '--passport', f.passport, '--stage', 'verifier', '--audit-report', audit], { encoding: 'utf8' });
    assert.equal(JSON.parse(scoped.stdout).status, 'PASS');
  } finally { cleanup(f); }
});






