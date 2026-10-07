#!/usr/bin/env node
// Read-only pre-seal metadata gate. It prevents hard-coded Passport/contract metadata.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

const args = {};
for (let i = 2; i < process.argv.length; i += 2) {
  if (!process.argv[i]?.startsWith('--') || !process.argv[i + 1]) {
    console.error('Usage: node handoff_metadata_consistency_check.js --product-root DIR --run-dir DIR --manifest FILE --passport FILE --contract FILE');
    process.exit(3);
  }
  args[process.argv[i].slice(2)] = process.argv[i + 1];
}
for (const key of ['product-root', 'run-dir', 'manifest', 'passport', 'contract']) {
  if (!args[key]) { console.error(`Missing --${key}`); process.exit(3); }
}
const findings = [];
const fail = (code, detail) => findings.push({ code, detail });
const sha = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex').toUpperCase();
const text = file => fs.readFileSync(file, 'utf8');
const field = (body, name) => body.match(new RegExp(`^${name}\\s*[:=]\\s*(.+)$`, 'mi'))?.[1]?.trim() || '';
const root = path.resolve(args['product-root']);
const runDir = path.resolve(args['run-dir']);
const manifestPath = path.resolve(args.manifest);
const passportPath = path.resolve(args.passport);
const contractPath = path.resolve(args.contract);
const artifactDir = fs.existsSync(manifestPath) ? path.dirname(manifestPath) : runDir;
for (const [label, file] of Object.entries({ manifest: manifestPath, passport: passportPath, contract: contractPath })) {
  if (!fs.existsSync(file)) fail('FILE_MISSING', `${label}: ${file}`);
}
if (findings.length) {
  console.log(JSON.stringify({ tool: 'handoff_metadata_consistency_check', version: '1.0', status: 'FAIL', findings }, null, 2));
  process.exit(2);
}
const manifest = text(manifestPath);
const passportSha = sha(passportPath);
const contractSha = sha(contractPath);
const contractVersion = text(contractPath).match(/^Версия\s*:\s*([^\s]+)/mi)?.[1] || text(contractPath).match(/^Version\s*:\s*([^\s]+)/mi)?.[1] || '';
const routeNames = {
  manifest: manifestPath,
  handoff: fs.readdirSync(artifactDir).find(n => /^collector_handoff__/i.test(n) && /\.md$/i.test(n)),
  preflight: fs.readdirSync(artifactDir).find(n => /^preflight_report__/i.test(n) && /\.md$/i.test(n)),
  binding: fs.readdirSync(artifactDir).find(n => /^package_seal_binding__/i.test(n) && /\.md$/i.test(n)),
};
const bodies = {};
for (const [role, value] of Object.entries(routeNames)) {
  const file = role === 'manifest' ? value : (value ? path.join(artifactDir, value) : null);
  if (!file || !fs.existsSync(file)) { fail('ROUTE_FILE_MISSING', role); continue; }
  bodies[role] = text(file);
}
const expectedPassportPath = passportPath;
for (const [role, body] of Object.entries(bodies)) {
  const declaredPath = field(body, 'passport_path') || field(body, 'passport_file') || field(body, 'passport');
  const declaredPassportSha = field(body, 'passport_sha256');
  const declaredContractVersion = field(body, 'contract_version');
  const declaredContractSha = field(body, 'contract_sha256');
  if (declaredPath && path.resolve(declaredPath) !== expectedPassportPath) fail('PASSPORT_PATH_DRIFT', `${role}: ${declaredPath} vs ${expectedPassportPath}`);
  if (declaredPassportSha && declaredPassportSha.toUpperCase() !== passportSha) fail('PASSPORT_SHA_DRIFT', `${role}: ${declaredPassportSha} vs ${passportSha}`);
  if (declaredContractVersion && declaredContractVersion !== contractVersion) fail('CONTRACT_VERSION_DRIFT', `${role}: ${declaredContractVersion} vs ${contractVersion}`);
  if (declaredContractSha && declaredContractSha.toUpperCase() !== contractSha) fail('CONTRACT_SHA_DRIFT', `${role}: ${declaredContractSha} vs ${contractSha}`);
  if (/Паспорт_SKU__[^\s/\\]*__v\d+\.md/i.test(body)) fail('LEGACY_PASSPORT_FILENAME', role);
}
const action = field(bodies.handoff || '', 'requested_action');
if (action && /Паспорт_SKU__[^\s/\\]*__v\d+\.md/i.test(action)) fail('REQUESTED_ACTION_LEGACY_PASSPORT_FILENAME', action);
console.log(JSON.stringify({ tool: 'handoff_metadata_consistency_check', version: '1.0', status: findings.length ? 'FAIL' : 'PASS', passport_path: passportPath, passport_sha256: passportSha, contract_version: contractVersion, contract_sha256: contractSha, findings }, null, 2));
process.exit(findings.length ? 2 : 0);
