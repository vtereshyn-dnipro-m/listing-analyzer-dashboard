#!/usr/bin/env node
// Read-only mechanical gate for returned-answer coverage and follow-up necessity.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const args = {};
for (let i = 2; i < process.argv.length; i += 2) {
  if (!process.argv[i]?.startsWith('--') || !process.argv[i + 1]) {
    console.error('Usage: node response_coverage_check.js --product-root DIR --coverage FILE --returned-source FILE --mode intake|outbound');
    process.exit(3);
  }
  args[process.argv[i].slice(2)] = process.argv[i + 1];
}
if (!args['product-root'] || !args.coverage || !args['returned-source'] || !['intake', 'outbound'].includes(args.mode)) {
  console.error('Required: product-root, coverage, returned-source, mode=intake|outbound.'); process.exit(3);
}
const findings = [];
const fail = (code, detail) => findings.push({ code, detail });
const real = p => fs.realpathSync(path.resolve(p));
let root;
try { root = real(args['product-root']); } catch (e) { console.error(e.message); process.exit(3); }
function inside(p, label) {
  try {
    const full = real(p);
    if (full !== root && !full.startsWith(root + path.sep)) { fail('PATH_OUTSIDE_PRODUCT_ROOT', `${label}: ${full}`); return null; }
    return full;
  } catch (e) { fail('FILE_MISSING', `${label}: ${p}`); return null; }
}
const coveragePath = inside(args.coverage, 'coverage');
const sourcePath = inside(args['returned-source'], 'returned-source');
let data;
if (coveragePath) {
  try { data = JSON.parse(fs.readFileSync(coveragePath, 'utf8')); }
  catch (e) { fail('COVERAGE_JSON_INVALID', e.message); }
}
if (data) {
  if (!Array.isArray(data.rows)) fail('COVERAGE_ROWS_MISSING', 'rows must be an array.');
  else {
    const ids = new Set();
    let received = 0, missing = 0, residual = 0;
    for (const [index, row] of data.rows.entries()) {
      const at = `rows[${index}]`;
      if (!row || typeof row !== 'object') { fail('COVERAGE_ROW_INVALID', at); continue; }
      if (!row.question_id || ids.has(row.question_id)) fail('QUESTION_ID_MISSING_OR_DUPLICATE', at);
      ids.add(row.question_id);
      if (row.source_artifact_id !== data.source_artifact_id) fail('ROW_SOURCE_LINK_MISMATCH', at);
      for (const key of ['source_artifact_id', 'answer_locator', 'response_received', 'stated_answer', 'evidence_sufficiency_reason', 'residual_evidence', 'same_intent_repeat', 'follow_up_question_id_or_none']) {
        if (!Object.hasOwn(row, key)) fail('COVERAGE_FIELD_MISSING', `${at}.${key}`);
      }
      if (typeof row.response_received !== 'boolean' || typeof row.same_intent_repeat !== 'boolean') fail('COVERAGE_BOOLEAN_INVALID', at);
      if (row.response_received) {
        received++;
        if (!String(row.stated_answer || '').trim()) fail('RECEIVED_ANSWER_EMPTY', at);
        if (!String(row.answer_locator || '').trim()) fail('ANSWER_LOCATOR_EMPTY', at);
      } else missing++;
      if (String(row.residual_evidence || '').trim()) residual++;
      const follow = row.follow_up_question_id_or_none && String(row.follow_up_question_id_or_none).toLowerCase() !== 'none';
      if (follow && row.same_intent_repeat) fail('REPEATED_QUESTION', `${at}: ${row.question_id}`);
      if (args.mode === 'outbound' && follow) {
        for (const key of ['blocked_deliverable_or_gate', 'mandatory_basis', 'decision_reason']) {
          if (!String(row[key] || '').trim()) fail('NECESSITY_FIELD_MISSING', `${at}.${key}`);
        }
        if (row.internal_resolution_checked !== true || typeof row.bounded_draft_possible !== 'boolean' || row.external_request_necessary !== true) {
          fail('OUTBOUND_NECESSITY_NOT_PROVEN', at);
        }
      }
    }
    for (const [key, actual] of [['received_response_count', received], ['missing_response_count', missing], ['residual_evidence_count', residual]]) {
      if (data[key] !== actual) fail('COVERAGE_COUNT_MISMATCH', `${key}: declared ${data[key]}, actual ${actual}`);
    }
  }
  if (!data.source_artifact_id || !/^[A-Fa-f0-9]{64}$/.test(data.source_sha256 || '')) fail('SOURCE_LINK_MISSING', 'Source ID/SHA missing.');
  else if (sourcePath) {
    const actual = crypto.createHash('sha256').update(fs.readFileSync(sourcePath)).digest('hex').toUpperCase();
    if (actual !== data.source_sha256.toUpperCase()) fail('SOURCE_HASH_MISMATCH', 'Returned source bytes differ from coverage record.');
  }
}
console.log(JSON.stringify({ tool: 'response_coverage_check', version: '1.0', mode: args.mode, status: findings.length ? 'FAIL' : 'PASS', findings }, null, 2));
process.exit(findings.length ? 2 : 0);
