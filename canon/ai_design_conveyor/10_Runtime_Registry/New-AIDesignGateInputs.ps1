[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$RunStatePath,
  [string]$EvidenceBundlePath,
  [Parameter(Mandatory=$true)][string]$OutputDirectory,
  [string]$EdgeRegistryPath=(Join-Path $PSScriptRoot 'AI_DESIGN_CORE_EDGE_REGISTRY.json'),
  [string]$ProviderRegistryPath=(Join-Path $PSScriptRoot 'AI_DESIGN_GATE_FACT_PROVIDER_REGISTRY.json'),
  [string]$GateInputSchemaPath=(Join-Path $PSScriptRoot 'ai_design_gate_input.schema.json'),
  [string]$EvidenceSchemaPath=(Join-Path $PSScriptRoot 'ai_design_gate_evidence_bundle.schema.json'),
  [string]$ManifestSchemaPath=(Join-Path $PSScriptRoot 'ai_design_gate_input_build_manifest.schema.json'),
  [string]$RunStateValidatorPath=(Join-Path $PSScriptRoot 'Test-AIDesignRunState.ps1')
)
$ErrorActionPreference='Stop';$version='1.0'
function J([string]$p){Get-Content -LiteralPath $p -Raw -Encoding UTF8|ConvertFrom-Json}
function Sha([string]$p){(Get-FileHash -Algorithm SHA256 -LiteralPath $p).Hash.ToLowerInvariant()}
function TextSha([string]$t){[Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes($t))).ToLowerInvariant()}
function State-Fact([string]$id,[object]$s,[string]$stateHash,[string]$graphVersion){
  $value=$null;$resolved=$true
  switch($id){
    'exact_product_identity_pinned'{$value=(-not[string]::IsNullOrWhiteSpace([string]$s.product_identity.sku) -and -not[string]::IsNullOrWhiteSpace([string]$s.product_identity.model) -and -not[string]::IsNullOrWhiteSpace([string]$s.product_identity.product_root))}
    'graph_version_pinned'{$value=(-not[string]::IsNullOrWhiteSpace([string]$s.pinned_graph.graph_version) -and @($s.pinned_graph.psobject.Properties.Name).Count -ge 5)}
    'exact_passport_available'{$value=(-not[string]::IsNullOrWhiteSpace([string]$s.pinned_product_truth.path) -and -not[string]::IsNullOrWhiteSpace([string]$s.pinned_product_truth.sha256))}
    'passport_readiness'{$value=[string]$s.pinned_product_truth.status}
    'attempts_remaining'{$value=([int]$s.budgets.retry.used -lt [int]$s.budgets.retry.maximum)}
    'cost_remaining'{$value=([decimal]$s.budgets.cost.spent -lt [decimal]$s.budgets.cost.approved)}
    'graph_version_compatible'{$value=([string]$s.pinned_graph.graph_version -eq $graphVersion)}
    'run_state_consistent'{$value=$true}
    'side_effects_reconciled'{$value=(@($s.side_effect_ledger|Where-Object{$_.status -eq 'UNKNOWN' -or $_.reconciliation_status -in @('PENDING','UNRESOLVED')}).Count -eq 0)}
    default{$resolved=$false}
  }
  if(-not $resolved){return $null}
  [pscustomobject][ordered]@{fact_id=$id;value=$value;evaluator_class='DETERMINISTIC';freshness_status='CURRENT';evidence_refs=@("RUN_STATE_SHA256:$stateHash")}
}
foreach($p in @($RunStatePath,$EdgeRegistryPath,$ProviderRegistryPath,$GateInputSchemaPath,$EvidenceSchemaPath,$ManifestSchemaPath,$RunStateValidatorPath)){if(-not(Test-Path -LiteralPath $p -PathType Leaf)){throw "Required file missing: $p"}}
if($EvidenceBundlePath -and -not(Test-Path -LiteralPath $EvidenceBundlePath -PathType Leaf)){throw "Evidence Bundle missing: $EvidenceBundlePath"}
if(Test-Path -LiteralPath $OutputDirectory){throw "Immutable output directory already exists: $OutputDirectory"}
$parent=Split-Path -Parent $OutputDirectory;if(-not(Test-Path -LiteralPath $parent -PathType Container)){throw "Output parent missing: $parent"}
$pwsh=(Get-Process -Id $PID).Path;& $pwsh -NoProfile -File $RunStateValidatorPath -RunStatePath $RunStatePath|Out-Host;if($LASTEXITCODE -ne 0){throw 'Run State validation failed.'}
$state=J $RunStatePath;$stateHash=Sha $RunStatePath;$edges=(J $EdgeRegistryPath).edges;$providers=(J $ProviderRegistryPath).providers
$bundle=$null;if($EvidenceBundlePath){if(-not(Test-Json -LiteralPath $EvidenceBundlePath -SchemaFile $EvidenceSchemaPath -ErrorAction Stop)){throw 'Evidence Bundle schema failed.'};$bundle=J $EvidenceBundlePath;if($bundle.run_id -ne $state.run_id -or $bundle.run_state_sha256 -ne $stateHash){throw 'Evidence Bundle is not bound to current Run State.'}}
$active=@($state.node_state.active_node_ids);$outgoing=@($edges|Where-Object{$_.source_node_id -in $active}|Sort-Object edge_id)
New-Item -ItemType Directory -Path $OutputDirectory|Out-Null
$outputs=@();$allUnresolved=[Collections.Generic.HashSet[string]]::new()
foreach($edge in $outgoing){
  $needed=[Collections.Generic.HashSet[string]]::new();foreach($atom in @($edge.guard_expression -split '\s+AND\s+')){if($atom -match '^([a-z][a-z0-9_]*)\s'){$null=$needed.Add($Matches[1])};if($atom -match '\s+IN\s+([a-z][a-z0-9_]*)$'){$null=$needed.Add($Matches[1])}}
  $facts=@();$unresolved=@()
  foreach($id in @($needed|Sort-Object)){
    $provider=$providers|Where-Object fact_id -eq $id;if($null -eq $provider){throw "No registered provider for $id"}
    $fact=$null
    if($provider.provider_kind -eq 'RUN_STATE_DERIVATION'){$fact=State-Fact $id $state $stateHash (J $ProviderRegistryPath).graph_version}
    else{
      $candidates=@($bundle.fact_evidence|Where-Object fact_id -eq $id)
      if($candidates.Count -gt 1){throw "Duplicate evidence for $id"}
      if($candidates.Count -eq 1){$ev=$candidates[0];$valid=($ev.provider_kind -eq $provider.provider_kind -and $ev.provider_artifact_type -eq $provider.authoritative_artifact_type -and $ev.evaluator_class -eq $provider.allowed_evaluator_class -and $ev.bound_run_id -eq $state.run_id -and $ev.bound_run_state_sha256 -eq $stateHash -and (Test-Path -LiteralPath $ev.source_ref -PathType Leaf) -and (Sha $ev.source_ref) -eq $ev.source_sha256 -and $ev.freshness_status -eq 'CURRENT');if($valid){$fact=[pscustomobject][ordered]@{fact_id=$id;value=$ev.value;evaluator_class=$ev.evaluator_class;freshness_status='CURRENT';evidence_refs=@($ev.evidence_refs)}}}
    }
    if($null -ne $fact){$facts+=$fact}else{$unresolved+=$id;$null=$allUnresolved.Add($id)}
  }
  $control=@($bundle.edge_controls|Where-Object edge_id -eq $edge.edge_id);if($control.Count -gt 1){throw "Duplicate edge control: $($edge.edge_id)"}
  if($control.Count -eq 1){$c=$control[0];$extra=@($c.required_receipt_results.receipt_type|Where-Object{$_ -notin @($edge.required_source_receipts)});if($extra.Count){throw "Unexpected receipt type for $($edge.edge_id): $($extra-join ',')"};$receipts=@($edge.required_source_receipts|ForEach-Object{$t=$_;$match=@($c.required_receipt_results|Where-Object receipt_type -eq $t);if($match.Count -eq 1){$match[0]}else{[pscustomobject][ordered]@{receipt_type=$t;status='MISSING';receipt_ref=$null}}});$trigger=$c.observed_trigger;$payload=$c.payload_result;$authority=$c.authority_result;$receiver=$c.receiver_precheck}
  else{$trigger=[ordered]@{status='UNRESOLVED';name=$null;evidence_refs=@()};$payload=[ordered]@{status='UNRESOLVED';evidence_refs=@()};$receipts=@($edge.required_source_receipts|ForEach-Object{[pscustomobject][ordered]@{receipt_type=$_;status='MISSING';receipt_ref=$null}});$authority=if($edge.target_node_id -eq 'N190_AI_CREATOR_PROVIDER_EXECUTION'){[ordered]@{status='UNRESOLVED';evidence_refs=@()}}else{[ordered]@{status='NOT_REQUIRED';evidence_refs=@()}};$receiver=[ordered]@{status='UNRESOLVED';evidence_refs=@()}}
  $idMaterial=$state.run_id+'|'+$stateHash+'|'+$edge.edge_id;$evalId='GATE-'+$state.run_id.Substring(4)+'-'+(TextSha $idMaterial).Substring(0,12).ToUpperInvariant()
  $input=[ordered]@{schema_version='1.0';evaluation_id=$evalId;run_id=$state.run_id;graph_version=$state.pinned_graph.graph_version;run_state_sha256=$stateHash;edge_id=$edge.edge_id;observed_trigger=$trigger;facts=@($facts);payload_result=$payload;required_receipt_results=@($receipts);authority_result=$authority;receiver_precheck=$receiver;requested_at=if($bundle){$bundle.created_at}else{$state.updated_at}}
  $path=Join-Path $OutputDirectory ("gate_input_$($edge.edge_id).json");$input|ConvertTo-Json -Depth 100|Set-Content -LiteralPath $path -Encoding UTF8 -NoNewline;if(-not(Test-Json -LiteralPath $path -SchemaFile $GateInputSchemaPath -ErrorAction Stop)){throw "Generated Gate Input schema failed: $($edge.edge_id)"}
  $outputs += [pscustomobject][ordered]@{edge_id=$edge.edge_id;path=[IO.Path]::GetFullPath($path);sha256=Sha $path;resolved_fact_ids=@($facts.fact_id|Sort-Object);unresolved_fact_ids=@($unresolved|Sort-Object)}
}
$buildId='GATEBUILD-'+$state.run_id.Substring(4)+'-'+(TextSha ($stateHash+'|'+(@($outgoing.edge_id)-join '|'))).Substring(0,12).ToUpperInvariant()
$manifest=[ordered]@{schema_version='1.0';build_id=$buildId;run_id=$state.run_id;run_state_sha256=$stateHash;active_node_ids=@($active);outputs=@($outputs);unresolved_fact_ids=@($allUnresolved|Sort-Object);external_side_effects_executed=0;created_at=if($bundle){$bundle.created_at}else{$state.updated_at};builder_version=$version}
$manifestPath=Join-Path $OutputDirectory 'gate_input_build_manifest.json';$manifest|ConvertTo-Json -Depth 100|Set-Content -LiteralPath $manifestPath -Encoding UTF8 -NoNewline;if(-not(Test-Json -LiteralPath $manifestPath -SchemaFile $ManifestSchemaPath -ErrorAction Stop)){throw 'Build Manifest schema failed.'}
Write-Host 'AI_DESIGN_GATE_INPUT_BUILD=PASS';Write-Host "BUILD_ID=$buildId";Write-Host "EDGES=$($outgoing.Count)";Write-Host "UNRESOLVED_FACTS=$($allUnresolved.Count)";Write-Host 'EXTERNAL_SIDE_EFFECTS=0';Write-Host "MANIFEST_PATH=$manifestPath"
