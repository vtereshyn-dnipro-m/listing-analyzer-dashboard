[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$InputPath,
    [Parameter(Mandatory=$true)][string]$OutputPath,
    [string]$RunStatePath = (Join-Path $PSScriptRoot 'ai_design_run_state.spec_fixture.json'),
    [string]$EdgeRegistryPath = (Join-Path $PSScriptRoot 'AI_DESIGN_CORE_EDGE_REGISTRY.json'),
    [string]$InputSchemaPath = (Join-Path $PSScriptRoot 'ai_design_gate_input.schema.json'),
    [string]$OutputSchemaPath = (Join-Path $PSScriptRoot 'ai_design_gate_evaluation.schema.json'),
    [string]$RunStateValidatorPath = (Join-Path $PSScriptRoot 'Test-AIDesignRunState.ps1')
)

$ErrorActionPreference = 'Stop'
$evaluatorVersion = '1.0'
function Read-Json([string]$Path) { Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json }
function Sha([string]$Path) { (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant() }
function Check([string]$Status, [object[]]$Evidence) { [pscustomobject][ordered]@{status=$Status;evidence_refs=@($Evidence)} }
function Parse-Literal([string]$Token) {
    if ($Token -eq 'true') { return $true }
    if ($Token -eq 'false') { return $false }
    $number = 0.0
    if ([double]::TryParse($Token, [Globalization.NumberStyles]::Float, [Globalization.CultureInfo]::InvariantCulture, [ref]$number)) { return $number }
    return $Token
}
function Find-Fact([object]$GateInput, [string]$FactId) {
    $matches = @($GateInput.facts | Where-Object fact_id -eq $FactId)
    if ($matches.Count -ne 1) { return $null }
    return $matches[0]
}
function Evaluate-Atom([string]$AtomText, [int]$Index, [object]$GateInput) {
    $operator = $null; $left = $null; $expected = $null; $rightFactId = $null
    if ($AtomText -match '^(?<left>[a-z][a-z0-9_]*)\s*==\s*(?<right>true|false|-?[0-9]+(?:\.[0-9]+)?|[A-Z][A-Z0-9_]*)$') {
        $left=$Matches.left; $operator='EQ'; $expected=Parse-Literal $Matches.right
    } elseif ($AtomText -match '^(?<left>[a-z][a-z0-9_]*)\s*>\s*(?<right>-?[0-9]+(?:\.[0-9]+)?)$') {
        $left=$Matches.left; $operator='GT'; $expected=Parse-Literal $Matches.right
    } elseif ($AtomText -match '^(?<left>[a-z][a-z0-9_]*)\s+IN\s+\[(?<items>[A-Z0-9_, ]+)\]$') {
        $left=$Matches.left; $operator='IN_SET'; $expected=@($Matches.items -split ',' | ForEach-Object { Parse-Literal $_.Trim() })
    } elseif ($AtomText -match '^(?<left>[a-z][a-z0-9_]*)\s+IN\s+(?<right>[a-z][a-z0-9_]*)$') {
        $left=$Matches.left; $operator='MEMBER_OF'; $rightFactId=$Matches.right
    } else { throw "Unsupported guard grammar atom: $AtomText" }

    $fact = Find-Fact $GateInput $left
    $status='UNRESOLVED'; $actual=$null; $evidence=@()
    if ($null -ne $fact) {
        $actual=$fact.value; $evidence=@($fact.evidence_refs)
        if ($fact.freshness_status -eq 'CURRENT') {
            switch ($operator) {
                'EQ' { $status = if ($actual -ceq $expected) {'PASS'} else {'FAIL'} }
                'GT' {
                    if ($actual -is [ValueType] -and $actual -isnot [bool]) { $status = if ([double]$actual -gt [double]$expected) {'PASS'} else {'FAIL'} }
                }
                'IN_SET' { $status = if (@($expected) -contains $actual) {'PASS'} else {'FAIL'} }
                'MEMBER_OF' {
                    $rightFact = Find-Fact $GateInput $rightFactId
                    if ($null -ne $rightFact) {
                        $expected=@($rightFact.value); $evidence=@($evidence + $rightFact.evidence_refs)
                        if ($rightFact.freshness_status -eq 'CURRENT' -and $rightFact.value -is [array]) { $status = if (@($rightFact.value) -contains $actual) {'PASS'} else {'FAIL'} }
                    }
                }
            }
        }
    }
    [pscustomobject][ordered]@{atom_id=('ATOM-{0:D2}' -f $Index);fact_id=$left;operator=$operator;expected_value=$expected;actual_value=$actual;status=$status;evidence_refs=@($evidence|Sort-Object -Unique)}
}

foreach ($path in @($InputPath,$RunStatePath,$EdgeRegistryPath,$InputSchemaPath,$OutputSchemaPath,$RunStateValidatorPath)) { if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Required file missing: $path" } }
if (Test-Path -LiteralPath $OutputPath) { throw "Immutable output already exists: $OutputPath" }
$outputParent = Split-Path -Parent $OutputPath
if (-not (Test-Path -LiteralPath $outputParent -PathType Container)) { throw "Output parent missing: $outputParent" }
if (-not (Test-Json -LiteralPath $InputPath -SchemaFile $InputSchemaPath -ErrorAction Stop)) { throw 'Gate input schema validation failed.' }
$pwsh=(Get-Process -Id $PID).Path
& $pwsh -NoProfile -File $RunStateValidatorPath -RunStatePath $RunStatePath | Out-Host
if ($LASTEXITCODE -ne 0) { throw 'Run State validation failed.' }

$gateInput=Read-Json $InputPath; $state=Read-Json $RunStatePath; $registry=Read-Json $EdgeRegistryPath
$stateHash=Sha $RunStatePath
if ($gateInput.run_id -ne $state.run_id -or $gateInput.graph_version -ne $state.pinned_graph.graph_version -or $gateInput.run_state_sha256.ToLowerInvariant() -ne $stateHash) { throw 'Gate input is not bound to the supplied Run State.' }
$edge=$registry.edges|Where-Object edge_id -eq $gateInput.edge_id
if ($null -eq $edge) { throw 'Gate edge is not registered.' }
if ($edge.source_node_id -notin @($state.node_state.active_node_ids)) { throw 'Gate edge source is not active.' }
if ($edge.edge_id -notin @($state.edge_state.available_edge_ids)) { throw 'Gate edge is not structurally available.' }

$triggerStatus = if ($gateInput.observed_trigger.status -eq 'UNRESOLVED') {'UNRESOLVED'} elseif ($gateInput.observed_trigger.status -eq 'PRESENT' -and $gateInput.observed_trigger.name -eq $edge.trigger) {'PASS'} else {'FAIL'}
$triggerResult=Check $triggerStatus $gateInput.observed_trigger.evidence_refs
$atomTexts=@($edge.guard_expression -split '\s+AND\s+')
$atomResults=@(); for($i=0;$i -lt $atomTexts.Count;$i++){ $atomResults += Evaluate-Atom $atomTexts[$i].Trim() ($i+1) $gateInput }
$guardStatus = if (@($atomResults|Where-Object status -eq 'FAIL').Count -gt 0) {'FAIL'} elseif (@($atomResults|Where-Object status -eq 'UNRESOLVED').Count -gt 0) {'UNRESOLVED'} else {'PASS'}
$guardEvidence=@($atomResults.evidence_refs|ForEach-Object{$_}|Sort-Object -Unique)
$guardResult=Check $guardStatus $guardEvidence

$expectedReceipts=@($edge.required_source_receipts|Sort-Object); $actualReceipts=@($gateInput.required_receipt_results.receipt_type|Sort-Object)
if (($expectedReceipts -join '|') -ne ($actualReceipts -join '|')) { throw 'Required receipt evaluation set does not match Edge Registry.' }
$reasons=[System.Collections.Generic.List[string]]::new()
if($triggerStatus -eq 'FAIL'){$reasons.Add('TRIGGER_FALSE')}elseif($triggerStatus -eq 'UNRESOLVED'){$reasons.Add('TRIGGER_UNRESOLVED')}
if($guardStatus -eq 'FAIL'){$reasons.Add('GUARD_FALSE')}elseif($guardStatus -eq 'UNRESOLVED'){$reasons.Add('GUARD_UNRESOLVED')}
if($gateInput.payload_result.status -eq 'FAIL'){$reasons.Add('PAYLOAD_INVALID')}elseif($gateInput.payload_result.status -eq 'UNRESOLVED'){$reasons.Add('PAYLOAD_UNRESOLVED')}
if(@($gateInput.required_receipt_results|Where-Object status -eq 'MISSING').Count){$reasons.Add('RECEIPT_MISSING')}
if(@($gateInput.required_receipt_results|Where-Object status -eq 'INVALID').Count){$reasons.Add('RECEIPT_INVALID')}
if($gateInput.authority_result.status -eq 'FAIL'){$reasons.Add('AUTHORITY_MISSING')}elseif($gateInput.authority_result.status -eq 'UNRESOLVED'){$reasons.Add('AUTHORITY_UNRESOLVED')}
if($gateInput.receiver_precheck.status -eq 'FAIL'){$reasons.Add('RECEIVER_NOT_READY')}elseif($gateInput.receiver_precheck.status -eq 'UNRESOLVED'){$reasons.Add('RECEIVER_UNRESOLVED')}
if($edge.target_node_id -eq 'N190_AI_CREATOR_PROVIDER_EXECUTION' -and $gateInput.authority_result.status -ne 'PASS'){$reasons.Add('AUTHORITY_MISSING')}
$eligible=$reasons.Count -eq 0
$result=[ordered]@{schema_version='1.0';evaluation_id=$gateInput.evaluation_id;input_ref=[IO.Path]::GetFullPath($InputPath);input_sha256=Sha $InputPath;run_id=$gateInput.run_id;graph_version=$gateInput.graph_version;run_state_sha256=$gateInput.run_state_sha256;edge_id=$edge.edge_id;trigger_result=$triggerResult;guard_result=$guardResult;atom_results=$atomResults;payload_result=$gateInput.payload_result;required_receipt_results=@($gateInput.required_receipt_results);authority_result=$gateInput.authority_result;receiver_precheck=$gateInput.receiver_precheck;eligible=$eligible;rejection_reason_codes=@($reasons|Sort-Object -Unique);evaluated_at=(Get-Date).ToUniversalTime().ToString('o');evaluator_version=$evaluatorVersion}
$temp=Join-Path $outputParent ([IO.Path]::GetRandomFileName())
try {
    $result|ConvertTo-Json -Depth 100|Set-Content -LiteralPath $temp -Encoding UTF8 -NoNewline
    if(-not(Test-Json -LiteralPath $temp -SchemaFile $OutputSchemaPath -ErrorAction Stop)){throw 'Gate output schema validation failed.'}
    Move-Item -LiteralPath $temp -Destination $OutputPath
} finally { if(Test-Path -LiteralPath $temp){Remove-Item -LiteralPath $temp -Force} }
Write-Host 'AI_DESIGN_GATE_EVALUATION=PASS'
Write-Host "EDGE_ID=$($edge.edge_id)"
Write-Host "TRIGGER=$triggerStatus"
Write-Host "GUARD=$guardStatus"
Write-Host "ELIGIBLE=$eligible"
Write-Host "OUTPUT_SHA256=$(Sha $OutputPath)"
