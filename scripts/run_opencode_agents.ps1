$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
New-Item -ItemType Directory -Force docs/agent-reports/logs | Out-Null
$agents = @(
  @{ Name = 'site-report-agent'; Branch = 'site-report'; Prompt = 'Implement Site Report according to docs/API_CONTRACTS.md and docs/AGENT_BOUNDARIES.md' },
  @{ Name = 'engineering-ai-agent'; Branch = 'engineering-ai'; Prompt = 'Implement Engineering AI according to docs/AI_ARCHITECTURE.md and docs/API_CONTRACTS.md' },
  @{ Name = 'acceptance-agent'; Branch = 'acceptance'; Prompt = 'Implement Acceptance according to docs/API_CONTRACTS.md and docs/AGENT_BOUNDARIES.md' }
)
$gitRoot = git rev-parse --show-toplevel 2>$null
$cleanGit = $LASTEXITCODE -eq 0 -and -not (git status --porcelain)
if ($cleanGit) {
  $runId = Get-Date -Format 'yyyyMMddHHmmss'
  foreach ($agent in $agents) {
    $agent.Dir = Join-Path $root ".worktrees/$($agent.Branch)"
    git worktree add -b "opencode/$($agent.Branch)-$runId" $agent.Dir HEAD
    if ($LASTEXITCODE -ne 0) { throw "Could not create worktree for $($agent.Name)" }
  }
  $jobs = foreach ($agent in $agents) {
    Start-Job -ArgumentList $root, $agent.Dir, $agent.Name, $agent.Prompt -ScriptBlock {
      param($rootPath, $cwd, $name, $prompt)
      Set-Location $cwd
      opencode run --model opencode-go/deepseek-v4.1-flash --agent $name --format json $prompt |
        Set-Content (Join-Path $rootPath "docs/agent-reports/logs/$name.jsonl")
      if ($LASTEXITCODE -ne 0) { throw "$name failed" }
    }
  }
  $jobs | Wait-Job | Out-Null
  $failed = $jobs | Where-Object State -ne 'Completed'
  $jobs | Receive-Job
  $jobs | Remove-Job
  if ($failed) { exit 1 }
  exit 0
}

# Shared directory without a clean Git checkout: do not run writers concurrently.
foreach ($agent in $agents) {
  opencode run --model opencode-go/deepseek-v4.1-flash --agent $agent.Name --format json $agent.Prompt |
    Set-Content "docs/agent-reports/logs/$($agent.Name).jsonl"
  if ($LASTEXITCODE -ne 0) { throw "$($agent.Name) failed" }
}
