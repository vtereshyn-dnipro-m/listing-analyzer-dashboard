#!/usr/bin/env node
// Read-only cross-file route and sealed-package integrity check.
// It does not repair files, issue receipts, or decide Product Truth.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

const args = {};
for (let i = 2; i < process.argv.length; i += 2) {
  if (!process.argv[i]?.startsWith('--') || !process.argv[i + 1]) {
    console.error('Usage: node handoff_integrity_check.js --product-root DIR --run-dir DIR --manifest FILE --base-manifest FILE [--passport FILE]');
    process.exit(3);
  }
  args[process.argv[i].slice(2)] = process.argv[i + 1];
}
if (!args['product-root'] || !args['run-dir'] || !args.manifest || !args['base-manifest']) {
  console.error('Missing --product-root, --run-dir, --manifest or --base-manifest'); process.exit(3);
}
const findings = [];
const fail = (code, detail) => findings.push({ code, detail });
const hash = p => crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex').toUpperCase();
const read = p => fs.readFileSync(p, 'utf8');
const runDir = path.resolve(args['run-dir']);
const manifestPath = path.resolve(args.manifest);
const productRoot = path.resolve(args['product-root']);
const hasBaseManifest = !/^none$/i.test(String(args['base-manifest']));
const baseManifestPath = hasBaseManifest ? path.resolve(args['base-manifest']) : null;
if (!fs.existsSync(runDir) || !fs.statSync(runDir).isDirectory()) fail('RUN_DIR_MISSING', runDir);
if (!fs.existsSync(manifestPath)) fail('MANIFEST_MISSING', manifestPath);
const artifactDir = fs.existsSync(manifestPath) ? path.dirname(manifestPath) : runDir;
if (fs.existsSync(manifestPath) && path.dirname(manifestPath) !== runDir) {
  // A run may contain multiple immutable revisions; inspect the revision that owns the manifest.
  // The caller still supplies the run root for traceability.
}
const safeRead = p => { try { return read(p); } catch { fail('FILE_MISSING', p); return ''; } };

let manifest = '';
if (fs.existsSync(manifestPath)) manifest = read(manifestPath);
const field = (body, name) => body.match(new RegExp(`^${name}\\s*:\\s*(.+)$`, 'mi'))?.[1]?.trim() || '';
const rev = field(manifest, 'revision') || field(manifest, 'package_revision');
const runFiles = fs.existsSync(artifactDir) ? fs.readdirSync(artifactDir) : [];
const findRole = role => runFiles.find(n => n.startsWith(role + '__') && /\.md$/i.test(n));
const bindingCandidates = runFiles.filter(n => /^package_seal_binding__/i.test(n) && /\.md$/i.test(n));
if (bindingCandidates.length > 1) fail('DUPLICATE_SEAL_BINDING_FILES', bindingCandidates.join(', '));
const staleBindingCandidates = runFiles.filter(n => /^package_seal_binding\.md$/i.test(n));
if (staleBindingCandidates.length) fail('STALE_SEAL_BINDING_FILE_PRESENT', staleBindingCandidates.join(', '));
const paths = {
  handoff: findRole('collector_handoff'),
  preflight: findRole('preflight_report'),
  binding: bindingCandidates[0],
};
for (const [role, name] of Object.entries(paths)) if (!name) fail('REQUIRED_ROUTE_FILE_MISSING', `${role} in ${artifactDir}`);
const bodies = Object.fromEntries(Object.entries(paths).map(([role, name]) => [role, name ? safeRead(path.join(artifactDir, name)) : '']));

const manifestParent = field(manifest, 'supersedes_manifest_sha256') || field(manifest, 'supersedes_package_sha256');
const handoffParent = field(bodies.handoff, 'supersedes_manifest_sha256') || field(bodies.handoff, 'supersedes_package_sha256');
const bindingParent = field(bodies.binding, 'supersedes_manifest_sha256') || field(bodies.binding, 'supersedes_package_sha256');
const preflightParent = field(bodies.preflight, 'supersedes_manifest_sha256') || field(bodies.preflight, 'supersedes_package_sha256');
const parents = { manifest: manifestParent, handoff: handoffParent, binding: bindingParent, preflight: preflightParent };
const nonemptyParents = Object.values(parents).filter(Boolean);
if (nonemptyParents.length && new Set(nonemptyParents).size !== 1) fail('PARENT_SHA_DRIFT', JSON.stringify(parents));

const baseId = field(manifest, 'base_package_id');
const baseSha = field(manifest, 'base_package_sha256');
if (!hasBaseManifest) {
  if ((baseId && !/^none\b/i.test(baseId)) || (baseSha && !/^none\b/i.test(baseSha))) {
    fail('INITIAL_BASE_DECLARATION_MISMATCH', `base_package_id=${baseId || '(empty)'}, base_package_sha256=${baseSha || '(empty)'}`);
  }
} else if (!fs.existsSync(baseManifestPath)) fail('BASE_MANIFEST_MISSING', baseManifestPath);
else if (baseId && baseSha) {
  const actualBaseId = field(read(baseManifestPath), 'package_id');
  if (actualBaseId !== baseId) fail('BASE_PACKAGE_ID_MISMATCH', `${baseId} vs ${actualBaseId}`);
  if (hash(baseManifestPath) !== baseSha.toUpperCase()) fail('BASE_PACKAGE_HASH_MISMATCH', `${baseId}: expected ${hash(baseManifestPath)}, declared ${baseSha}`);
}

const scopes = {
  manifest: field(manifest, 'audit_scope') || field(manifest, 'scope'),
  handoff: field(bodies.handoff, 'audit_scope') || field(bodies.handoff, 'requested_action'),
  binding: field(bodies.binding, 'audit_scope') || field(bodies.binding, 'requested_action'),
};
const scopeText = Object.values(scopes).filter(Boolean).join(' | ');
if (/source_delta_targeted_audit/i.test(scopeText) && /TARGETED_CHG_CANDIDATE_AUDIT/i.test(scopeText)) fail('AUDIT_SCOPE_DRIFT', JSON.stringify(scopes));

const packageRevision = field(manifest, 'package_revision') || rev;
for (const [role, body] of Object.entries(bodies)) {
  if (!body) continue;
  const declared = field(body, 'package_revision') || field(body, 'revision');
  if (declared && packageRevision && declared !== packageRevision) fail('REVISION_DRIFT', `${role}: ${declared} vs manifest ${packageRevision}`);
}
if (args.passport && !fs.existsSync(args.passport)) fail('PASSPORT_MISSING', path.resolve(args.passport));
if (args.passport && fs.existsSync(args.passport)) {
  const passportBody = read(args.passport);
  if (/\bSource ID\s*\|\s*SOURCE-/i.test(passportBody)) fail('SOURCE_ID_PREFIX_MISMATCH', 'Passport uses archive filename prefix as source ID.');
  if (/extension_field/i.test(passportBody)) {
    for (const required of ['extension_id', 'source_label', 'value', 'scope', 'source_artifact_id', 'locator', 'status', 'extension_reason']) {
      if (!new RegExp(`\\b${required}\\b`, 'i').test(passportBody)) fail('EXTENSION_FIELD_METADATA_MISSING', required);
    }
  }
}
const evidenceName = runFiles.find(n => n.startsWith('evidence_artifact_manifest__') && /\.md$/i.test(n));
if (evidenceName) {
  const evidenceBody = read(path.join(artifactDir, evidenceName));
  if (/source_id\s*[:=]\s*UNKNOWN\b/i.test(evidenceBody)) fail('EVIDENCE_SOURCE_UNKNOWN', evidenceName);
  if (/role\s*[:=]\s*EXTRACTED_SOURCE_MEMBER\b/i.test(evidenceBody) && /(?:origin|parent(?:_id)?)\s*[:=]\s*(?:$|UNKNOWN\b)/im.test(evidenceBody)) fail('EVIDENCE_PARENT_MISSING', evidenceName);
}
if (manifest && !/package_admissible_for_audit\s*[:=]\s*true\b/i.test(manifest)) fail('PACKAGE_NOT_ADMISSIBLE', 'Manifest is not admissible.');
if (bodies.preflight && !/PF-STATE-RECONCILIATION[^|]*\|\s*PASS/i.test(bodies.preflight)) fail('STATE_RECONCILIATION_NOT_PASS', 'Preflight lacks passing PF-STATE-RECONCILIATION.');

console.log(JSON.stringify({ tool: 'handoff_integrity_check', version: '1.0', run_dir: runDir, manifest: manifestPath, status: findings.length ? 'FAIL' : 'PASS', findings }, null, 2));
process.exit(findings.length ? 2 : 0);
