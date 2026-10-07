#!/usr/bin/env node
// Read-only structural preflight. It does not decide Product Truth or issue receipts.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const zlib = require('node:zlib');
const args = {};
for (let i = 2; i < process.argv.length; i += 2) {
  if (!process.argv[i]?.startsWith('--') || !process.argv[i + 1]) {
    console.error('Usage: node passport_package_check.js --product-root DIR --run-dir DIR --passport FILE [--profile-approval FILE] [--stage collector|auditor|verifier] [--audit-report FILE]');
    process.exit(3);
  }
  args[process.argv[i].slice(2)] = process.argv[i + 1];
}
const stage = args.stage || 'collector';
if (!['collector', 'auditor', 'verifier'].includes(stage) || !args['product-root'] || !args['run-dir'] || !args.passport) {
  console.error('Missing required input or invalid stage.'); process.exit(3);
}
const findings = [];
const diagnostics = [];
const fail = (code, detail) => findings.push({ code, detail });
const diagnose = (code, detail) => diagnostics.push({ code, detail });
const read = p => fs.readFileSync(p, 'utf8');
const hash = p => crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex').toUpperCase();
const real = p => fs.realpathSync(path.resolve(p));
function decodeXml(xml) {
  return xml.replace(/<w:tab\b[^>]*\/>/g, '\t').replace(/<w:(?:br|cr)\b[^>]*\/>/g, '\n')
    .replace(/<\/w:p>/g, '\n').replace(/<[^>]+>/g, '')
    .replace(/&#x([0-9a-f]+);/gi, (_, n) => String.fromCodePoint(parseInt(n, 16)))
    .replace(/&#([0-9]+);/g, (_, n) => String.fromCodePoint(parseInt(n, 10)))
    .replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'").replace(/&amp;/g, '&');
}
function readDocxText(file) {
  const zip = fs.readFileSync(file);
  let eocd = -1;
  for (let i = zip.length - 22; i >= Math.max(0, zip.length - 65557); i--) {
    if (zip.readUInt32LE(i) === 0x06054b50) { eocd = i; break; }
  }
  if (eocd < 0) throw new Error('DOCX ZIP end record missing');
  const entries = zip.readUInt16LE(eocd + 10);
  let pos = zip.readUInt32LE(eocd + 16);
  for (let i = 0; i < entries; i++) {
    if (zip.readUInt32LE(pos) !== 0x02014b50) throw new Error('DOCX central directory invalid');
    const method = zip.readUInt16LE(pos + 10);
    const compressedSize = zip.readUInt32LE(pos + 20);
    const nameLength = zip.readUInt16LE(pos + 28);
    const extraLength = zip.readUInt16LE(pos + 30);
    const commentLength = zip.readUInt16LE(pos + 32);
    const localOffset = zip.readUInt32LE(pos + 42);
    const name = zip.subarray(pos + 46, pos + 46 + nameLength).toString('utf8');
    if (name === 'word/document.xml') {
      if (zip.readUInt32LE(localOffset) !== 0x04034b50) throw new Error('DOCX local header invalid');
      const localNameLength = zip.readUInt16LE(localOffset + 26);
      const localExtraLength = zip.readUInt16LE(localOffset + 28);
      const start = localOffset + 30 + localNameLength + localExtraLength;
      const compressed = zip.subarray(start, start + compressedSize);
      const xml = method === 0 ? compressed : method === 8 ? zlib.inflateRawSync(compressed) : null;
      if (!xml) throw new Error(`Unsupported DOCX compression method ${method}`);
      return decodeXml(xml.toString('utf8'));
    }
    pos += 46 + nameLength + extraLength + commentLength;
  }
  throw new Error('word/document.xml missing');
}
function readPassportText(file) {
  return path.extname(file).toLowerCase() === '.docx' ? readDocxText(file) : read(file);
}
let root;
try { root = real(args['product-root']); } catch (e) { console.error(e.message); process.exit(3); }
function inside(p, label) {
  try {
    const full = real(p);
    if (full !== root && !full.startsWith(root + path.sep)) { fail('PATH_OUTSIDE_PRODUCT_ROOT', `${label}: ${full}`); return null; }
    return full;
  } catch (e) { fail('FILE_MISSING', `${label}: ${p}`); return null; }
}
const runDir = inside(args['run-dir'], 'run-dir');
const passport = inside(args.passport, 'passport');
if (passport && fs.statSync(passport).isFile()) {
  try {
    const body = readPassportText(passport);
    if (!/Паспорт.*SKU|SKU.*Паспорт/i.test(body)) fail('PASSPORT_IDENTITY_MISSING', 'Passport title missing.');
    if (!/\b(NOT_READY|BLOCKED|READY_WITH_LIMITATIONS|READY)\b/.test(body)) fail('PASSPORT_STATE_MISSING', 'Allowed state missing.');
    if (/чернетк|черновик|проекц|projection/i.test(path.basename(passport))) fail('SEPARATE_PASSPORT_DRAFT', path.basename(passport));
  } catch (e) {
    diagnose('PASSPORT_FORMAT_UNREADABLE', `${path.basename(passport)}: ${e.message}; direct read-back required`);
  }
} else if (passport) fail('PASSPORT_FILE_INVALID', passport);
const roles = ['source_manifest', 'candidate_update', 'collector_handoff', 'change_events', 'package_manifest'];
const files = {};
if (runDir && fs.statSync(runDir).isDirectory()) {
  const names = fs.readdirSync(runDir);
  for (const role of roles) {
    const matches = names.filter(n => n.startsWith(role + '__') && n.endsWith('.md'));
    if (matches.length !== 1) fail('CORE_FILE_COUNT', `${role}: ${matches.length}`);
    else files[role] = inside(path.join(runDir, matches[0]), role);
  }
  for (const name of names.filter(n => /\.(md|docx|pdf)$/i.test(n))) {
    const looksLikeProductPassport = /^(?:Паспорт(?:[_\s-]*SKU)?|SKU[_\s-]*Passport)/i.test(name) || /(?:чернетк|черновик|проекц|projection).*(?:паспорт|passport)|(?:паспорт|passport).*(?:чернетк|черновик|проекц|projection)/i.test(name);
    if (looksLikeProductPassport && !/^passport_section_matrix__/i.test(name) && path.resolve(runDir, name) !== passport && !Object.values(files).some(p => p && path.basename(p) === name)) fail('UNAPPROVED_PASSPORT_DOCUMENT', name);
  }
}
if (files.package_manifest) {
  const manifest = read(files.package_manifest);
  for (const role of roles.slice(0, 4)) {
    const rows = manifest.split(/\r?\n/).filter(s => s.startsWith('|') && s.includes(`| ${role} |`));
    if (rows.length !== 1) { fail('MANIFEST_ROLE_COUNT', `${role}: ${rows.length}`); continue; }
    const cells = rows[0].split('|').slice(1, -1).map(s => s.trim());
    const declared = inside(cells[1], `manifest:${role}`);
    if (!declared || !files[role]) continue;
    if (declared !== files[role]) diagnose('MANIFEST_PATH_MISMATCH', role);
    if (Number(cells[2]) !== fs.statSync(files[role]).size) diagnose('MANIFEST_SIZE_MISMATCH', role);
    if (cells[3]?.toUpperCase() !== hash(files[role])) diagnose('MANIFEST_HASH_MISMATCH', role);
  }
  if (!/package_admissible_for_audit=true\b/i.test(manifest)) diagnose('PACKAGE_NOT_ADMISSIBLE_DECLARATION', 'Manifest does not declare audit admissibility; receiver must decide from registered content gates.');
  const pHash = manifest.match(/passport_sha256\s*[:=]\s*([A-Fa-f0-9]{64})/i);
  if (!/passport_id\s*[:=]/i.test(manifest) || !pHash) diagnose('PASSPORT_MANIFEST_LINK_MISSING', 'Passport ID/SHA missing.');
  else if (passport && pHash[1].toUpperCase() !== hash(passport)) diagnose('PASSPORT_HASH_MISMATCH', 'Passport bytes differ.');
  const contractFile = path.join(__dirname, '..', '00A_Контракт_передач_Паспорта_SKU.md');
  const contractVersion = read(contractFile).match(/^Версия:\s*([^\s]+)/m)?.[1];
  const pinnedVersion = manifest.match(/contract_version\s*[:=]\s*([^\s;]+)/i)?.[1];
  const pinnedHash = manifest.match(/contract_sha256\s*[:=]\s*([A-Fa-f0-9]{64})/i)?.[1];
  if (!pinnedVersion || !pinnedHash) diagnose('CONTRACT_PIN_MISSING', 'Contract version/SHA missing.');
  else if (pinnedVersion !== contractVersion || pinnedHash.toUpperCase() !== hash(contractFile)) diagnose('CONTRACT_PIN_MISMATCH', 'Manifest does not pin the current 00A bytes/version.');
}
if (runDir && fs.statSync(runDir).isDirectory()) {
  const canonicalGateFiles = [
    '00A_Контракт_передач_Паспорта_SKU.md',
    '02_Агент_собиратель_Паспорта_SKU.md',
    '02A_Системный_промпт_агента_собирателя_Паспорта_SKU.md',
    '02C_Контракт_выхода_агента_собирателя.md',
    '03_Агент_аудитор_качества_Паспорта_SKU.md'
  ];
  const registeredPfCodes = new Set();
  for (const file of canonicalGateFiles) {
    for (const match of read(path.join(__dirname, '..', file)).matchAll(/PF-[A-Z0-9-]+/g)) registeredPfCodes.add(match[0]);
  }
  const reports = fs.readdirSync(runDir).filter(n => n.startsWith('preflight_report__') && n.endsWith('.md'));
  if (reports.length !== 1) fail('PREFLIGHT_REPORT_COUNT', `expected 1, found ${reports.length}`);
  else {
    const rows = [...read(path.join(runDir, reports[0])).matchAll(/^\|\s*(PF-[A-Z0-9-]+)\s*\|\s*([^|]+)\|/gm)];
    if (!rows.length) fail('PREFLIGHT_RESULTS_MISSING', 'No PF rows.');
    for (const row of rows) {
      if (row[2].trim().toUpperCase() === 'PASS') continue;
      if (registeredPfCodes.has(row[1])) fail('PREFLIGHT_NOT_PASS', `${row[1]}=${row[2].trim()}`);
      else diagnose('UNREGISTERED_PREFLIGHT_CODE', `${row[1]}=${row[2].trim()}; non-operative under 00A`);
    }
    if (!rows.some(row => row[1] === 'PF-STATE-RECONCILIATION')) fail('STATE_RECONCILIATION_NOT_TESTED', 'Required gate absent.');
  }
}
if (args['profile-approval'] && files.candidate_update) {
  const approval = inside(args['profile-approval'], 'profile-approval');
  if (approval) {
    try {
      const profile = JSON.parse(read(approval));
      if (profile.profile_version && profile.field_count > 0) {
        const candidate = read(files.candidate_update);
        if (/^\|\s*GAP-[^|]*\|[^\n]*(profile absent|profile missing|профил[ья] отсутств)/im.test(candidate) ||
            /^\|\s*REQ-[^|]*\|[^\n]*(provide versioned category profile|предоставить.*профил)/im.test(candidate)) fail('STALE_PROFILE_REQUEST', 'Approved profile exists but is requested again.');
      }
    } catch (e) { fail('PROFILE_APPROVAL_INVALID', e.message); }
  }
}
if (stage === 'verifier') {
  const audit = args['audit-report'] && inside(args['audit-report'], 'audit-report');
  if (!audit) fail('AUDIT_REPORT_REQUIRED', 'Verifier input needs audit report.');
  else {
    const body = read(audit);
    for (const [field, pattern] of [['handoff_scope', /\S+/], ['handoff_verdict', /READY_FOR_VERIFIER\b/i], ['input_receipt', /ACCEPTED\b/i]]) {
      if (!new RegExp(`${field}\\s*[:=]\\s*${pattern.source}`, pattern.flags || 'i').test(body)) fail('FULL_AUDIT_ACCEPTANCE_MISSING', `${field} missing.`);
    }
    const pinned = body.match(/collector_package_sha256\s*[:=]\s*([A-Fa-f0-9]{64})/i);
    if (files.package_manifest && (!pinned || pinned[1].toUpperCase() !== hash(files.package_manifest))) fail('AUDIT_PACKAGE_HASH_MISMATCH', 'Audit does not pin this collector manifest.');
  }
}
console.log(JSON.stringify({ tool: 'passport_package_check', version: '1.1', stage, product_root: root, status: findings.length ? 'FAIL' : 'PASS', findings, diagnostics }, null, 2));
process.exit(findings.length ? 2 : 0);


