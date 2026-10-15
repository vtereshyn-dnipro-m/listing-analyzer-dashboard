[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$InputStatePath,
    [Parameter(Mandatory=$true)][string]$DecisionPath,
    [Parameter(Mandatory=$true)][string]$OutputStatePath,
    [Parameter(Mandatory=$true)][string]$ReceiptPath,
    [string]$EdgeRegistryPath = (Join-Path $PSScriptRoot 'AI_DESIGN_CORE_EDGE_REGISTRY.json'),
    [string]$RunStateValidatorPath = (Join-Path $PSScriptRoot 'Test-AIDesignRunState.ps1'),
    [string]$RouterValidatorPath = (Join-Path $PSScriptRoot 'Test-AIDesignRouterDecision.ps1'),
    [string]$ReceiptSchemaPath = (Join-Path $PSScriptRoot 'ai_design_transition_receipt.schema.json')
)

$ErrorActionPreference = 'Stop'
$writerVersion = '1.0'

function Read-Json([string]$Path) { Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json }
function Get-Sha([string]$Path) { (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant() }
function Get-TextSha([string]$Text) {
    $bytes = [Text.Encoding]::UTF8.GetBytes($Text)
    $hash = [Security.Cryptography.SHA256]::HashData($bytes)
    return [Convert]::ToHexString($hash).ToLowerInvariant()
}
function Json([object]$Value) { $Value | ConvertTo-Json -Depth 100 }
function Unique([object[]]$Values) { @($Values | Where-Object { $null -ne $_ -and "$_" -ne '' } | Sort-Object -Unique) }
function Remove-Value([object[]]$Values, [string]$Value) { @($Values | Where-Object { $_ -ne $Value }) }
function Add-Value([object[]]$Values, [string]$Value) { Unique @($Values + $Value) }
function Assert-NewTarget([string]$Path, [string]$Label) {
    if (Test-Path -LiteralPath $Path) { throw "$Label already exists; immutable output cannot be overwritten: $Path" }
    $parent = Split-Path -Parent $Path
    if ([string]::IsNullOrWhiteSpace($parent) -or -not (Test-Path -LiteralPath $parent -PathType Container)) { throw "$Label parent directory does not exist: $parent" }
}

foreach ($path in @($InputStatePath,$DecisionPath,$EdgeRegistryPath,$RunStateValidatorPath,$RouterValidatorPath,$ReceiptSchemaPath)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Required input missing: $path" }
}
Assert-NewTarget $OutputStatePath 'Output state'
Assert-NewTarget $ReceiptPath 'Transition receipt'

$pwsh = (Get-Process -Id $PID).Path
& $pwsh -NoProfile -File $RunStateValidatorPath -RunStatePath $InputStatePath | Out-Host
if ($LASTEXITCODE -ne 0) { throw 'Input Run State validation failed.' }
& $pwsh -NoProfile -File $RouterValidatorPath -DecisionPath $DecisionPath -RunStatePath $InputStatePath | Out-Host
if ($LASTEXITCODE -ne 0) { throw 'Router Decision validation failed.' }

$state = Read-Json $InputStatePath
$decision = Read-Json $DecisionPath
$edgeRegistry = Read-Json $EdgeRegistryPath
$inputHash = Get-Sha $InputStatePath
$decisionHash = Get-Sha $DecisionPath
$edgeRegistryHash = Get-Sha $EdgeRegistryPath

if ($decision.outcome -ne 'EDGE_SELECTED' -or [string]::IsNullOrWhiteSpace([string]$decision.selected_edge_id)) { throw 'Writer accepts only EDGE_SELECTED.' }
if ($decision.run_state_sha256.ToLowerInvariant() -ne $inputHash) { throw 'Decision Run State hash drift.' }
$edge = $edgeRegistry.edges | Where-Object edge_id -eq $decision.selected_edge_id
if ($null -eq $edge) { throw 'Selected edge is not registered.' }
if ($edge.edge_id -notin @($state.edge_state.available_edge_ids)) { throw 'Selected edge is no longer state-available.' }
if ($edge.source_node_id -notin @($state.node_state.active_node_ids)) { throw 'Selected edge source is no longer active.' }

$openBlockers = @($state.blockers | Where-Object status -eq 'OPEN')
foreach ($blocker in $openBlockers) {
    if ($edge.edge_id -notin @($blocker.allowed_recovery_edge_ids)) { throw "Open blocker $($blocker.blocker_id) does not allow selected recovery edge." }
}

$next = Json $state | ConvertFrom-Json
$sequence = @($next.transition_history).Count + 1
$transitionId = 'TRANSITION-{0}-{1:D4}' -f $state.run_id,$sequence
$checkpointId = 'CHECKPOINT-{0}-{1:D4}' -f $state.run_id,$sequence
$now = (Get-Date).ToUniversalTime().ToString('o')
$receiptRef = [IO.Path]::GetFullPath($ReceiptPath)

if ($edge.state_delta.complete_source_node) {
    $next.node_state.active_node_ids = @(Remove-Value $next.node_state.active_node_ids $edge.source_node_id)
    $next.node_state.completed_node_ids = @(Add-Value $next.node_state.completed_node_ids $edge.source_node_id)
}
if ($edge.state_delta.activate_target_node) {
    $next.node_state.completed_node_ids = @(Remove-Value $next.node_state.completed_node_ids $edge.target_node_id)
    $next.node_state.pending_node_ids = @(Remove-Value $next.node_state.pending_node_ids $edge.target_node_id)
    $next.node_state.blocked_node_ids = @(Remove-Value $next.node_state.blocked_node_ids $edge.target_node_id)
    $next.node_state.not_applicable_node_ids = @(Remove-Value $next.node_state.not_applicable_node_ids $edge.target_node_id)
    $next.node_state.active_node_ids = @(Add-Value $next.node_state.active_node_ids $edge.target_node_id)
    $next.node_state.current_node_id = $edge.target_node_id
}

$next.edge_state.available_edge_ids = @(Remove-Value $next.edge_state.available_edge_ids $edge.edge_id)
$next.edge_state.rejected_edge_ids = @(Remove-Value $next.edge_state.rejected_edge_ids $edge.edge_id)
$next.edge_state.unevaluated_edge_ids = @(Remove-Value $next.edge_state.unevaluated_edge_ids $edge.edge_id)
$next.edge_state.applied_edge_ids = @(Add-Value $next.edge_state.applied_edge_ids $edge.edge_id)

foreach ($blocker in @($next.blockers | Where-Object status -eq 'OPEN')) {
    if ($edge.edge_id -in @($blocker.allowed_recovery_edge_ids)) { $blocker.status = 'RESOLVED' }
}
$remainingOpenBlockers = @($next.blockers | Where-Object status -eq 'OPEN')
$next.lifecycle_state = if ($remainingOpenBlockers.Count -gt 0) { 'RUN_BLOCKED' } else { $edge.state_delta.set_run_state }

$activeNodes = @($next.node_state.active_node_ids)
$outgoing = @($edgeRegistry.edges | Where-Object { $_.source_node_id -in $activeNodes } | Select-Object -ExpandProperty edge_id)
$next.edge_state.available_edge_ids = @(Unique @($outgoing | Where-Object { $_ -notin @($next.edge_state.applied_edge_ids) -and $_ -notin @($next.edge_state.rejected_edge_ids) }))
$next.edge_state.unevaluated_edge_ids = @(Unique @($edgeRegistry.edges.edge_id | Where-Object { $_ -notin @($next.edge_state.applied_edge_ids) -and $_ -notin @($next.edge_state.rejected_edge_ids) -and $_ -notin @($next.edge_state.available_edge_ids) }))

$transitionEvent = [ordered]@{
    transition_id = $transitionId; decision_id = $decision.decision_id; edge_id = $edge.edge_id
    source_node_id = $edge.source_node_id; target_node_id = $edge.target_node_id
    input_state_sha256 = $inputHash; decision_sha256 = $decisionHash; receipt_ref = $receiptRef; applied_at = $now
}
$next.transition_history = @($next.transition_history) + [pscustomobject]$transitionEvent
$next.receipt_refs = @(Add-Value $next.receipt_refs $receiptRef)
$next.updated_at = $now

$checkpointPayloadHash = Get-TextSha (Json $next)
$artifactBindingHash = Get-TextSha (Json @($next.artifacts))
$sideEffectLedgerHash = Get-TextSha (Json @($next.side_effect_ledger))
$next.latest_checkpoint = [pscustomobject][ordered]@{
    checkpoint_id = $checkpointId; state_sha256 = $checkpointPayloadHash
    artifact_binding_sha256 = $artifactBindingHash; side_effect_ledger_sha256 = $sideEffectLedgerHash
    created_at = $now; created_by_node_id = $edge.target_node_id; receipt_ref = $receiptRef
}
$resumeEdges = @($next.edge_state.available_edge_ids)
$needsReconciliation = @($next.side_effect_ledger | Where-Object { $_.status -in @('STARTED','UNKNOWN') -or $_.reconciliation_status -in @('PENDING','UNRESOLVED') }).Count -gt 0
$next.resume_cursor = if ($resumeEdges.Count -gt 0) {
    [pscustomobject][ordered]@{checkpoint_id=$checkpointId;resume_node_id=$edge.target_node_id;allowed_resume_edge_ids=$resumeEdges;reconciliation_required=$needsReconciliation}
} else { $null }

$outputTemp = Join-Path (Split-Path -Parent $OutputStatePath) ([IO.Path]::GetRandomFileName())
$receiptTemp = Join-Path (Split-Path -Parent $ReceiptPath) ([IO.Path]::GetRandomFileName())
try {
    Json $next | Set-Content -LiteralPath $outputTemp -Encoding UTF8 -NoNewline
    $outputHash = Get-Sha $outputTemp
    $receipt = [ordered]@{
        schema_version='1.0'; transition_id=$transitionId; run_id=$state.run_id; graph_version=$state.pinned_graph.graph_version
        decision_id=$decision.decision_id; edge_id=$edge.edge_id; source_node_id=$edge.source_node_id; target_node_id=$edge.target_node_id
        input_state_path=[IO.Path]::GetFullPath($InputStatePath); input_state_sha256=$inputHash
        decision_path=[IO.Path]::GetFullPath($DecisionPath); decision_sha256=$decisionHash; edge_registry_sha256=$edgeRegistryHash
        output_state_path=[IO.Path]::GetFullPath($OutputStatePath); output_state_sha256=$outputHash
        checkpoint_id=$checkpointId; checkpoint_payload_sha256=$checkpointPayloadHash; artifact_binding_sha256=$artifactBindingHash; side_effect_ledger_sha256=$sideEffectLedgerHash
        state_delta_applied=[ordered]@{lifecycle_state=$next.lifecycle_state;source_completed=[bool]$edge.state_delta.complete_source_node;target_activated=[bool]$edge.state_delta.activate_target_node;artifact_status_updates=@($edge.state_delta.artifact_status_updates)}
        verdict='TRANSITION_APPLIED'; applied_at=$now; writer_version=$writerVersion
    }
    Json $receipt | Set-Content -LiteralPath $receiptTemp -Encoding UTF8 -NoNewline
    if (-not (Test-Json -LiteralPath $receiptTemp -SchemaFile $ReceiptSchemaPath -ErrorAction Stop)) { throw 'Transition receipt schema validation failed.' }
    & $pwsh -NoProfile -File $RunStateValidatorPath -RunStatePath $outputTemp | Out-Host
    if ($LASTEXITCODE -ne 0) { throw 'Output Run State validation failed.' }
    Move-Item -LiteralPath $receiptTemp -Destination $ReceiptPath
    Move-Item -LiteralPath $outputTemp -Destination $OutputStatePath
} finally {
    if (Test-Path -LiteralPath $outputTemp) { Remove-Item -LiteralPath $outputTemp -Force }
    if (Test-Path -LiteralPath $receiptTemp) { Remove-Item -LiteralPath $receiptTemp -Force }
}

Write-Host 'AI_DESIGN_STATE_TRANSITION=PASS'
Write-Host "TRANSITION_ID=$transitionId"
Write-Host "EDGE_ID=$($edge.edge_id)"
Write-Host "OUTPUT_STATE_SHA256=$(Get-Sha $OutputStatePath)"
Write-Host "RECEIPT_PATH=$([IO.Path]::GetFullPath($ReceiptPath))"
