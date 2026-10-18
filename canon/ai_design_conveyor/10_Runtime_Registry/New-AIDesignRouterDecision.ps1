[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$RunStatePath,
  [string[]]$GateEvaluationPaths=@(),
  [Parameter(Mandatory=$true)][string]$OutputPath,
  [string]$EdgeRegistryPath=(Join-Path $PSScriptRoot 'AI_DESIGN_CORE_EDGE_REGISTRY.json'),
  [string]$DecisionSchemaPath=(Join-Path $PSScriptRoot 'ai_design_router_decision.schema.json'),
  [string]$RunStateValidatorPath=(Join-Path $PSScriptRoot 'Test-AIDesignRunState.ps1'),
  [string]$GateValidatorPath=(Join-Path $PSScriptRoot 'Test-AIDesignGateEvaluation.ps1')
)
$ErrorActionPreference='Stop';$routerVersion='1.0'
function J([string]$p){Get-Content -LiteralPath $p -Raw -Encoding UTF8|ConvertFrom-Json}
function Sha([string]$p){(Get-FileHash -Algorithm SHA256 -LiteralPath $p).Hash.ToLowerInvariant()}
function TextSha([string]$t){[Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes($t))).ToLowerInvariant()}
foreach($p in @($RunStatePath,$EdgeRegistryPath,$DecisionSchemaPath,$RunStateValidatorPath,$GateValidatorPath)+@($GateEvaluationPaths)){if(-not(Test-Path -LiteralPath $p -PathType Leaf)){throw "Required file missing: $p"}}
if(Test-Path -LiteralPath $OutputPath){throw "Immutable output already exists: $OutputPath"}
$parent=Split-Path -Parent $OutputPath;if(-not(Test-Path -LiteralPath $parent -PathType Container)){throw "Output parent missing: $parent"}
$pwsh=(Get-Process -Id $PID).Path
& $pwsh -NoProfile -File $RunStateValidatorPath -RunStatePath $RunStatePath|Out-Host;if($LASTEXITCODE -ne 0){throw 'Run State validation failed.'}
$state=J $RunStatePath;$registry=J $EdgeRegistryPath;$stateHash=Sha $RunStatePath
$active=@($state.node_state.active_node_ids);$expected=@($registry.edges|Where-Object{$_.source_node_id -in $active}|Select-Object -ExpandProperty edge_id|Sort-Object)
$evaluations=@()
foreach($path in $GateEvaluationPaths){
  $gate=J $path
  & $pwsh -NoProfile -File $GateValidatorPath -EvaluationPath $path -InputPath $gate.input_ref -RunStatePath $RunStatePath -EdgeRegistryPath $EdgeRegistryPath|Out-Host
  if($LASTEXITCODE -ne 0){throw "Gate Evaluation validation failed: $path"}
  $evaluations += [pscustomobject]@{path=[IO.Path]::GetFullPath($path);hash=Sha $path;gate=$gate}
}
$actual=@($evaluations.gate.edge_id|Sort-Object)
if(($actual|Sort-Object -Unique).Count -ne $actual.Count){throw 'Duplicate Gate Evaluation edge.'}
if(($expected-join '|') -ne ($actual-join '|')){throw "Gate Evaluation set mismatch. Expected: $($expected-join ','); actual: $($actual-join ',')"}
$candidates=@()
foreach($edgeId in $expected){
  $edge=$registry.edges|Where-Object edge_id -eq $edgeId;$entry=$evaluations|Where-Object{$_.gate.edge_id -eq $edgeId};$g=$entry.gate
  if($g.run_id -ne $state.run_id -or $g.graph_version -ne $state.pinned_graph.graph_version -or $g.run_state_sha256 -ne $stateHash){throw "$edgeId Gate Evaluation identity mismatch."}
  $candidates += [pscustomobject][ordered]@{edge_id=$edge.edge_id;source_node_id=$edge.source_node_id;target_node_id=$edge.target_node_id;registered=$true;state_available=($edge.edge_id -in @($state.edge_state.available_edge_ids));gate_evaluation_ref=$entry.path;gate_evaluation_sha256=$entry.hash;trigger_result=$g.trigger_result;guard_result=$g.guard_result;payload_result=$g.payload_result;required_receipt_results=@($g.required_receipt_results);authority_result=$g.authority_result;receiver_precheck=$g.receiver_precheck;eligible=[bool]$g.eligible;rejection_reason_codes=@($g.rejection_reason_codes)}
}
$eligible=@($candidates|Where-Object eligible);$outcome=$null;$selected=$null;$reason=$null;$blocker=$null;$human=$false
if($state.terminal.is_terminal){$outcome='NO_OP_TERMINAL';$reason='TERMINAL_STATE'}
elseif($eligible.Count -eq 1){$outcome='EDGE_SELECTED';$selected=$eligible[0].edge_id;$reason='SINGLE_ELIGIBLE_EDGE'}
elseif($eligible.Count -gt 1){$outcome='HUMAN_ROUTE_DECISION';$reason='MULTIPLE_ELIGIBLE_EDGES';$human=$true}
else{
  $outcome='RUN_BLOCKED'
  if($expected.Count -eq 0){$reason='NO_REGISTERED_EDGE';$blocker='UNROUTABLE_CASE'}
  elseif(@($candidates|Where-Object{$_.guard_result.status -eq 'UNRESOLVED' -or $_.trigger_result.status -eq 'UNRESOLVED'}).Count){$reason='GUARD_UNRESOLVED';$blocker='GUARD_UNRESOLVED'}
  elseif(@($candidates|Where-Object{$_.payload_result.status -eq 'FAIL' -or $_.payload_result.status -eq 'UNRESOLVED'}).Count){$reason='REQUIRED_PAYLOAD_INVALID';$blocker='REQUIRED_PAYLOAD_INVALID'}
  elseif(@($candidates.required_receipt_results|ForEach-Object{$_}|Where-Object status -ne 'PASS').Count){$reason='REQUIRED_RECEIPT_MISSING';$blocker='REQUIRED_RECEIPT_MISSING'}
  elseif(@($candidates|Where-Object{$_.authority_result.status -in @('FAIL','UNRESOLVED')}).Count){$reason='AUTHORITY_MISSING';$blocker='SIDE_EFFECT_AUTHORITY_MISSING'}
  elseif(@($candidates|Where-Object{$_.receiver_precheck.status -in @('FAIL','UNRESOLVED')}).Count){$reason='RECEIVER_NOT_READY';$blocker='RECEIVER_NOT_ACCEPTED'}
  else{$reason='NO_ELIGIBLE_EDGE';$blocker='UNROUTABLE_CASE'}
}
$gateHashes=@($evaluations.hash|Sort-Object);$decisionKey=TextSha ($stateHash+'|'+($gateHashes-join '|'))
$decisionId=('ROUTE-{0}-{1}' -f $state.run_id,$decisionKey.Substring(0,12).ToUpperInvariant())
$createdAt=if($evaluations.Count){@($evaluations.gate.evaluated_at|Sort-Object)[-1]}else{$state.updated_at}
$decision=[ordered]@{schema_version='1.0';decision_id=$decisionId;run_id=$state.run_id;graph_version=$state.pinned_graph.graph_version;run_state_sha256=$stateHash;router_version=$routerVersion;active_node_ids=@($active);candidate_evaluations=@($candidates);outcome=$outcome;selected_edge_id=$selected;reason_code=$reason;blocker_code=$blocker;human_decision_required=$human;decision_created_at=$createdAt}
$temp=Join-Path $parent ([IO.Path]::GetRandomFileName())
try{$decision|ConvertTo-Json -Depth 100|Set-Content -LiteralPath $temp -Encoding UTF8 -NoNewline;if(-not(Test-Json -LiteralPath $temp -SchemaFile $DecisionSchemaPath -ErrorAction Stop)){throw 'Decision schema failed.'};Move-Item -LiteralPath $temp -Destination $OutputPath}finally{if(Test-Path -LiteralPath $temp){Remove-Item -LiteralPath $temp -Force}}
Write-Host 'AI_DESIGN_ROUTER_ASSEMBLY=PASS';Write-Host "DECISION_ID=$decisionId";Write-Host "CANDIDATES=$($candidates.Count)";Write-Host "ELIGIBLE=$($eligible.Count)";Write-Host "OUTCOME=$outcome";Write-Host "SELECTED_EDGE=$selected";Write-Host "OUTPUT_SHA256=$(Sha $OutputPath)"
