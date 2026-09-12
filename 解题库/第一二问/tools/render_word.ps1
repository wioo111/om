param([Parameter(Mandatory=$true)][string]$InputDocx, [Parameter(Mandatory=$true)][string]$OutputPdf)
$ErrorActionPreference='Stop'
$sourcePath=(Resolve-Path -LiteralPath $InputDocx).Path
$outputPath=[IO.Path]::GetFullPath($OutputPdf)
$targetDirectory=Split-Path -Parent $outputPath
New-Item -ItemType Directory -Path $targetDirectory -Force | Out-Null
$app=$null
$doc=$null
try {
    $app=New-Object -ComObject Word.Application
    $app.Visible=$false
    $app.DisplayAlerts=0
    $doc=$app.Documents.Open($sourcePath,$false,$true)
    $doc.ExportAsFixedFormat($outputPath,17)
    Write-Output "WORD_NATIVE_EXPORT_OK $outputPath"
} finally {
    if($null -ne $doc){$doc.Close(0);[void][Runtime.InteropServices.Marshal]::ReleaseComObject($doc)}
    if($null -ne $app){$app.Quit();[void][Runtime.InteropServices.Marshal]::ReleaseComObject($app)}
}
