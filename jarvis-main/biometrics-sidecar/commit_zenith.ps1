$sourceDir = "c:\Users\nnssp\Desktop\LEON\Zenith"
$targetDir = "c:\Users\nnssp\Desktop\ai-daemon\zenith_repo"

# Ensure target dir is a git repo
if (-not (Test-Path "$targetDir\.git")) {
    Push-Location $targetDir
    git init
    Pop-Location
}

# Get all source files excluding junk
$files = Get-ChildItem -Path $sourceDir -Recurse -File | Where-Object { 
    $_.FullName -notmatch 'node_modules|\\.git|dist|__pycache__|\\.venv' 
}

Write-Host "Found $($files.Count) files to process."

$count = 0
foreach ($file in $files) {
    # Get relative path reliably
    $relativePath = $file.FullName.Substring($sourceDir.Length).TrimStart('\')
    $targetPath = Join-Path $targetDir $relativePath
    $targetParent = Split-Path $targetPath -Parent

    # Ensure target directory exists
    if (-not (Test-Path $targetParent)) {
        New-Item -ItemType Directory -Path $targetParent -Force | Out-Null
    }

    # Copy file
    Copy-Item $file.FullName $targetPath -Force

    # Git operations
    Push-Location $targetDir
    git add $relativePath
    if ($LASTEXITCODE -eq 0) {
        git commit -m "Initialize $relativePath" | Out-Null
        if ($LASTEXITCODE -eq 0) {
            $count++
        } else {
            Write-Warning "Failed to commit $relativePath"
        }
    } else {
        Write-Warning "Failed to add $relativePath"
    }
    Pop-Location

    if ($count % 50 -eq 0 -and $count -gt 0) {
        Write-Host "Committed $count files..."
    }
    
    if ($count -ge 300) { break } 
}

Write-Host "Completed $count successful commits."
