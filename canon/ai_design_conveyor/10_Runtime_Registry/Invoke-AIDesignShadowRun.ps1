[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$RunStatePath,
  [string[]]$GateInputPaths=@(),
  [string]$EvidenceBundlePath,
  [Parameter(Mandatory=$true)][string]$OutputDirectory,
  [string]$ExpectedLegacyOutcome,
  [string]$ExpectedLegacyEdgeId,
  [string]$GateEvaluatorPath=(Join-Path $PSScriptRoot 'Invoke-AIDesignGateEvaluation.ps1'),
  [string]$GateInputBuilderPath=(Join-Path $PSScriptRoot 'New-AIDesignGateInputs.ps1'),
  [string]$RouterAssemblerPath=(Join-Path $PSScriptRoot 'New-AIDesignRouterDecision.ps1'),
  [string]$TransitionWriterPath=(Join-Path $PSScriptRoot 'Invoke-AIDesignStateTransition.ps1'),
  [string]$RunStateValidatorPath=(Join-Path $PSScriptRoot 'Test-AIDesignRunState.ps1'),
  [string]$RouterValidatorPath=(Join-Path $PSScriptRoot 'Test-AIDesignRouterDecision.ps1'),
  [string]$ReportSchemaPath=(Join-Path $PSScriptRoot 'ai_design_shadow_run_report.schema.json')
)
$ErrorActionPreference='Stop';$runnerVersion='1.0'
function J([string]$p){Get-Content -LiteralPath $p -Raw -Encoding UTF8|ConvertFrom-Json}
function Sha([string]$p){(Get-FileHash -Algorithm SHA256 -LiteralPath $p).Hash.ToLowerInvariant()}
function TextSha([string]$t){[Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes($t))).ToLowerInvariant()}
foreach($p in @($RunStatePath,$GateEvaluatorPath,$GateInputBuilderPath,$RouterAssemblerPath,$TransitionWriterPath,$RunStateValidatorPath,$RouterValidatorPath,$ReportSchemaPath)+@($GateInputPaths)){if(-not(Test-Path -LiteralPath $p -PathType Leaf)){throw "Required file missing: $p"}}
if($EvidenceBundlePath -and -not(Test-Path -LiteralPath $EvidenceBundlePath -PathType Leaf)){throw "Evidence Bundle missing: $EvidenceBundlePath"}
if($EvidenceBundlePath -and @($GateInputPaths).Count){throw 'Provide EvidenceBundlePath or GateInputPaths, not both.'}
if(Test-Path -LiteralPath $OutputDirectory){throw "Immutable shadow output directory already exists: $OutputDirectory"}
$parent=Split-Path -Parent $OutputDirectory;if(-not(Test-Path -LiteralPath $parent -PathType Container)){throw "Shadow output parent missing: $parent"}
New-Item -ItemType Directory -Path $OutputDirectory|Out-Null
$pwsh=(Get-Process -Id $PID).Path
& $pwsh -NoProfile -File $RunStateValidatorPath -RunStatePath $RunStatePath|Out-Host;if($LASTEXITCODE -ne 0){throw 'Run State validation failed.'}
$state=J $RunStatePath;$stateHash=Sha $RunStatePath
$builtInputManifest=$null
if($EvidenceBundlePath){
  $builtInputDirectory=Join-Path $OutputDirectory 'built_gate_inputs'
  & $GateInputBuilderPath -RunStatePath $RunStatePath -EvidenceBundlePath $EvidenceBundlePath -OutputDirectory $builtInputDirectory|Out-Host
  $builtInputManifestPath=Join-Path $builtInputDirectory 'gate_input_build_manifest.json'
  if(-not(Test-Path -LiteralPath $builtInputManifestPath -PathType Leaf)){throw 'Gate Input Builder did not create a manifest.'}
  $builtInputManifest=J $builtInputManifestPath;$GateInputPaths=@($builtInputManifest.outputs.path)
}
$inputBindings=@();$evaluationBindings=@();$evaluationPaths=@()
foreach($inputPath in @($GateInputPaths)){
  $gateInput=J $inputPath;$safeEdge=$gateInput.edge_id -replace '[^A-Z0-9_]','_';$evaluationPath=Join-Path $OutputDirectory ("gate_evaluation_{0}.json" -f $safeEdge)
  & $pwsh -NoProfile -File $GateEvaluatorPath -InputPath $inputPath -OutputPath $evaluationPath -RunStatePath $RunStatePath|Out-Host
  if($LASTEXITCODE -ne 0){throw "Gate evaluation failed: $inputPath"}
  $inputBindings += [pscustomobject][ordered]@{path=[IO.Path]::GetFullPath($inputPath);sha256=Sha $inputPath}
  $evaluationBindings += [pscustomobject][ordered]@{path=[IO.Path]::GetFullPath($evaluationPath);sha256=Sha $evaluationPath}
  $evaluationPaths += $evaluationPath
}
$decisionPath=Join-Path $OutputDirectory 'router_decision.json'
$assemblerParams=@{RunStatePath=$RunStatePath;OutputPath=$decisionPath;GateEvaluationPaths=@($evaluationPaths)}
& $RouterAssemblerPath @assemblerParams | Out-Host
if(-not(Test-Path -LiteralPath $decisionPath -PathType Leaf)){throw 'Router assembly failed.'}
& $pwsh -NoProfile -File $RouterValidatorPath -DecisionPath $decisionPath -RunStatePath $RunStatePath|Out-Host;if($LASTEXITCODE -ne 0){throw 'Router Decision validation failed.'}
$decision=J $decisionPath
$transitionPerformed=$false;$nextStatePath=$null;$nextStateHash=$null;$receiptPath=$null;$receiptHash=$null
if($decision.outcome -eq 'EDGE_SELECTED'){
  $nextStatePath=Join-Path $OutputDirectory 'simulated_next_state.json';$receiptPath=Join-Path $OutputDirectory 'simulated_transition_receipt.json'
  & $pwsh -NoProfile -File $TransitionWriterPath -InputStatePath $RunStatePath -DecisionPath $decisionPath -OutputStatePath $nextStatePath -ReceiptPath $receiptPath|Out-Host
  if($LASTEXITCODE -ne 0){throw 'Simulated transition failed.'}
  $transitionPerformed=$true;$nextStateHash=Sha $nextStatePath;$receiptHash=Sha $receiptPath
}
$comparison='NOT_PROVIDED'
if(-not [string]::IsNullOrWhiteSpace($ExpectedLegacyOutcome)){
  $outcomeMatch=$decision.outcome -eq $ExpectedLegacyOutcome
  $edgeMatch=if([string]::IsNullOrWhiteSpace($ExpectedLegacyEdgeId)){$null -eq $decision.selected_edge_id}else{$decision.selected_edge_id -eq $ExpectedLegacyEdgeId}
  $comparison=if($outcomeMatch -and $edgeMatch){'MATCH'}else{'MISMATCH'}
}
$shadowVerdict=if($comparison -eq 'MATCH'){'MATCH'}elseif($comparison -eq 'MISMATCH'){'DIVERGENCE'}else{'NO_REFERENCE'}
$identityMaterial=$stateHash+'|'+(@($evaluationBindings.sha256|Sort-Object)-join '|')+'|'+$ExpectedLegacyOutcome+'|'+$ExpectedLegacyEdgeId
$shadowId='SHADOW-{0}-{1}' -f $state.run_id,(TextSha $identityMaterial).Substring(0,12).ToUpperInvariant()
$createdAt=if($evaluationPaths.Count){@($evaluationPaths|ForEach-Object{(J $_).evaluated_at}|Sort-Object)[-1]}else{$state.updated_at}
$report=[ordered]@{schema_version='1.0';shadow_run_id=$shadowId;execution_mode='GRAPH_SHADOW_RUN';source_run_id=$state.run_id;source_state_path=[IO.Path]::GetFullPath($RunStatePath);source_state_sha256=$stateHash;gate_inputs=@($inputBindings);gate_evaluations=@($evaluationBindings);router_decision=[ordered]@{path=[IO.Path]::GetFullPath($decisionPath);sha256=Sha $decisionPath;outcome=$decision.outcome;selected_edge_id=$decision.selected_edge_id};simulated_transition=[ordered]@{performed=$transitionPerformed;state_path=if($nextStatePath){[IO.Path]::GetFullPath($nextStatePath)}else{$null};state_sha256=$nextStateHash;receipt_path=if($receiptPath){[IO.Path]::GetFullPath($receiptPath)}else{$null};receipt_sha256=$receiptHash};legacy_comparison=[ordered]@{expected_outcome=if($ExpectedLegacyOutcome){$ExpectedLegacyOutcome}else{$null};expected_edge_id=if($ExpectedLegacyEdgeId){$ExpectedLegacyEdgeId}else{$null};result=$comparison};external_side_effects_executed=0;shadow_verdict=$shadowVerdict;created_at=$createdAt;runner_version=$runnerVersion}
$reportPath=Join-Path $OutputDirectory 'shadow_run_report.json';$temp=Join-Path $OutputDirectory ([IO.Path]::GetRandomFileName())
try{$report|ConvertTo-Json -Depth 100|Set-Content -LiteralPath $temp -Encoding UTF8 -NoNewline;if(-not(Test-Json -LiteralPath $temp -SchemaFile $ReportSchemaPath -ErrorAction Stop)){throw 'Shadow report schema failed.'};Move-Item -LiteralPath $temp -Destination $reportPath}finally{if(Test-Path -LiteralPath $temp){Remove-Item -LiteralPath $temp -Force}}
Write-Host 'AI_DESIGN_SHADOW_RUN=PASS';Write-Host "SHADOW_RUN_ID=$shadowId";Write-Host "OUTCOME=$($decision.outcome)";Write-Host "SELECTED_EDGE=$($decision.selected_edge_id)";Write-Host "LEGACY_COMPARISON=$comparison";Write-Host "EXTERNAL_SIDE_EFFECTS=0";Write-Host "REPORT_PATH=$reportPath"
