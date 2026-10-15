[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$RequestPath,[Parameter(Mandatory=$true)][string]$OutputPath,[string]$PolicyPath=(Join-Path $PSScriptRoot 'AI_DESIGN_REWORK_TERMINATION_POLICY.json'))
$ErrorActionPreference='Stop';if(Test-Path $OutputPath){throw "Immutable receipt exists: $OutputPath"};$q=Get-Content $RequestPath -Raw|ConvertFrom-Json;$p=Get-Content $PolicyPath -Raw|ConvertFrom-Json;$l=$q.ledger|ConvertTo-Json -Depth 30|ConvertFrom-Json
function Stop-Budget([string]$code,[string]$verdict='TERMINATION_BUDGET_EXHAUSTED'){$script:reason=$code;$script:verdict=$verdict;$l.terminal.is_terminal=$true;$l.terminal.status='FAILED_EXHAUSTED';$l.terminal.reason_code=$code}
$verdict='TERMINATION_BUDGET_ALLOW';$reason=$null
if($l.terminal.is_terminal){Stop-Budget 'COUNTER_RESET_REJECTED' 'COUNTER_RESET_REJECTED'}
elseif(-not$q.automatic_transition){if($q.event_class-ne'HUMAN_WAIT'){Stop-Budget 'ZERO_PROGRESS_TRANSITION_REJECTED' 'ZERO_PROGRESS_TRANSITION_REJECTED'}}
else{
  $l.automatic_transitions.used=[int]$l.automatic_transitions.used+1
  if($l.automatic_transitions.used-gt$l.automatic_transitions.maximum){Stop-Budget 'RUN_AUTOMATIC_TRANSITION_BUDGET_EXHAUSTED'}
  if($verdict-eq'TERMINATION_BUDGET_ALLOW'-and$q.event_class-ne'FORWARD'){$l.package_rework.used=[int]$l.package_rework.used+1;if($l.package_rework.used-gt$l.package_rework.maximum){Stop-Budget 'PACKAGE_REWORK_BUDGET_EXHAUSTED'}}
  if($verdict-eq'TERMINATION_BUDGET_ALLOW'-and$q.asset_id){$a=$l.asset_budgets.PSObject.Properties[$q.asset_id].Value;if($null-eq$a){throw 'ASSET_BUDGET_MISSING'}
    if($q.event_class-eq'REWORK'){$a.rework.used++;if($a.rework.used-gt$a.rework.maximum){Stop-Budget 'ASSET_REWORK_BUDGET_EXHAUSTED'}}
    if($q.event_class-eq'UPSTREAM_REENTRY'){$a.upstream_reentries.used++;if($a.upstream_reentries.used-gt$a.upstream_reentries.maximum){Stop-Budget 'UPSTREAM_REENTRY_LIMIT_EXHAUSTED'}}
    if($q.event_class-eq'QA_EVIDENCE_REFRESH'){$a.qa_evidence_refreshes.used++;if($a.qa_evidence_refreshes.used-gt$a.qa_evidence_refreshes.maximum){Stop-Budget 'QA_EVIDENCE_REFRESH_LIMIT_EXHAUSTED'}}
    if($q.normalized_defect_fingerprint-and-not$l.defect_registry.PSObject.Properties[$q.normalized_defect_fingerprint]){$a.distinct_defect_fingerprints.used++;$l.defect_registry|Add-Member -NotePropertyName $q.normalized_defect_fingerprint -NotePropertyValue ([pscustomobject]@{normalized_fingerprint=$q.normalized_defect_fingerprint;asset_id=$q.asset_id;first_seen_at=(Get-Date).ToUniversalTime().ToString('o');occurrences=1});if($a.distinct_defect_fingerprints.used-gt$a.distinct_defect_fingerprints.maximum){Stop-Budget 'DISTINCT_DEFECT_BUDGET_EXHAUSTED'}}
  }
  if($verdict-eq'TERMINATION_BUDGET_ALLOW'-and$q.incident_id){$i=$l.incident_budgets.PSObject.Properties[$q.incident_id].Value;if($null-eq$i){throw 'INCIDENT_BUDGET_MISSING'}
    if($q.event_class-eq'RECLASSIFICATION'){if(-not$q.new_evidence){Stop-Budget 'ZERO_PROGRESS_TRANSITION_REJECTED' 'ZERO_PROGRESS_TRANSITION_REJECTED'}else{$i.reclassifications.used++;if($i.reclassifications.used-gt$i.reclassifications.maximum){Stop-Budget 'RECLASSIFICATION_LIMIT_EXHAUSTED'}}}
    if($q.event_class-eq'CHECKPOINT_RESUME'){$i.checkpoint_resumes.used++;if($i.checkpoint_resumes.used-gt$i.checkpoint_resumes.maximum){Stop-Budget 'CHECKPOINT_RESUME_LIMIT_EXHAUSTED'}}
    if($q.event_class-eq'OWNER_APPROVED_RESUME'){$i.owner_approved_resumes.used++;if($i.owner_approved_resumes.used-gt$i.owner_approved_resumes.maximum){Stop-Budget 'OWNER_RESUME_LIMIT_EXHAUSTED'}}
  }
}
$l.revision=[int]$l.revision+1;$l.updated_at=(Get-Date).ToUniversalTime().ToString('o');$r=[ordered]@{schema_version='1.0';receipt_id="TERMBUDGET-$($q.request_id)";request_id=$q.request_id;edge_id=$q.edge_id;verdict=$verdict;reason_code=$reason;ledger=$l;evaluated_at=$l.updated_at};$r|ConvertTo-Json -Depth 40|Set-Content $OutputPath -Encoding UTF8 -NoNewline;Write-Output "AI_DESIGN_TERMINATION_BUDGET=$verdict"
