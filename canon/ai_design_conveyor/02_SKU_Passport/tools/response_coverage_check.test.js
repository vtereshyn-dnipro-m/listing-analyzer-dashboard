const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');
const script = path.join(__dirname, 'response_coverage_check.js');
function fixture() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'response-check-test-'));
  const source = path.join(root, 'returned.txt');
  fs.writeFileSync(source, 'answer');
  const coverage = path.join(root, 'response_coverage.json');
  const data = {
    source_artifact_id: 'SRC-1',
    source_sha256: crypto.createHash('sha256').update(fs.readFileSync(source)).digest('hex'),
    received_response_count: 1, missing_response_count: 0, residual_evidence_count: 1,
    rows: [{ question_id: 'Q-1', source_artifact_id: 'SRC-1', answer_locator: 'block Q-1', response_received: true,
      stated_answer: '8.2 kg', evidence_sufficiency_reason: 'old source conflicts', residual_evidence: 'corrected source',
      same_intent_repeat: false, follow_up_question_id_or_none: 'Q-2' }]
  };
  fs.writeFileSync(coverage, JSON.stringify(data));
  return { root, source, coverage, data };
}
function run(f, mode) {
  const result = spawnSync(process.execPath, [script, '--product-root', f.root, '--coverage', f.coverage, '--returned-source', f.source, '--mode', mode], { encoding: 'utf8' });
  return JSON.parse(result.stdout);
}
function cleanup(f) {
  const temp = fs.realpathSync(os.tmpdir());
  const actual = fs.realpathSync(f.root);
  assert.ok(actual.startsWith(temp + path.sep) && path.basename(actual).startsWith('response-check-test-'));
  fs.rmSync(actual, { recursive: true, force: true });
}
test('accepts complete returned-answer receipt', () => {
  const f = fixture();
  try { assert.equal(run(f, 'intake').status, 'PASS'); } finally { cleanup(f); }
});
test('blocks outbound when necessity fields are missing', () => {
  const f = fixture();
  try { assert.ok(run(f, 'outbound').findings.some(v => v.code === 'OUTBOUND_NECESSITY_NOT_PROVEN')); }
  finally { cleanup(f); }
});
test('accepts explicit necessity record but rejects repeated intent', () => {
  const f = fixture();
  try {
    Object.assign(f.data.rows[0], { blocked_deliverable_or_gate: 'verified mass', mandatory_basis: 'mandatory claim',
      internal_resolution_checked: true, bounded_draft_possible: true, external_request_necessary: true,
      decision_reason: 'new corrected source required for verified claim' });
    fs.writeFileSync(f.coverage, JSON.stringify(f.data));
    assert.equal(run(f, 'outbound').status, 'PASS');
    f.data.rows[0].same_intent_repeat = true;
    fs.writeFileSync(f.coverage, JSON.stringify(f.data));
    assert.ok(run(f, 'outbound').findings.some(v => v.code === 'REPEATED_QUESTION'));
  } finally { cleanup(f); }
});
