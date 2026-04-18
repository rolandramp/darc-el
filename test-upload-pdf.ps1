param(
    [Parameter(Mandatory = $true)]
    [string[]]$PdfPath,

    [string]$ApiBaseUrl = "http://localhost:8000",

    [int]$TimeoutSeconds = 120
)

$ErrorActionPreference = "Stop"

try {
    Add-Type -AssemblyName "System.Net.Http" -ErrorAction Stop
}
catch {
    throw "Could not load System.Net.Http. Please run this script in a PowerShell session with .NET support. Details: $($_.Exception.Message)"
}

function New-MultipartFormData {
    param(
        [string[]]$Files
    )

    $multipart = New-Object System.Net.Http.MultipartFormDataContent

    foreach ($file in $Files) {
        $resolved = Resolve-Path -Path $file -ErrorAction Stop
        $fullPath = $resolved.Path

        if (-not (Test-Path -Path $fullPath -PathType Leaf)) {
            throw "File does not exist: $fullPath"
        }

        if ([System.IO.Path]::GetExtension($fullPath).ToLowerInvariant() -ne ".pdf") {
            throw "Only .pdf files are allowed by this helper script: $fullPath"
        }

        $stream = [System.IO.File]::OpenRead($fullPath)
        $content = New-Object System.Net.Http.StreamContent($stream)
        $content.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::Parse("application/pdf")

        $fileName = [System.IO.Path]::GetFileName($fullPath)
        $multipart.Add($content, "files", $fileName)
    }

    # Keep the multipart container as a single object; otherwise PowerShell may enumerate it.
    return ,$multipart
}

$uploadUri = "$($ApiBaseUrl.TrimEnd('/'))/upload"
$httpClient = [System.Net.Http.HttpClient]::new()
$httpClient.Timeout = [TimeSpan]::FromSeconds($TimeoutSeconds)

$multipartContent = $null

try {
    $multipartContent = New-MultipartFormData -Files $PdfPath
    $response = $httpClient.PostAsync($uploadUri, $multipartContent).GetAwaiter().GetResult()
    $responseBody = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()

    Write-Host "StatusCode: $($response.StatusCode)"

    if (-not $response.IsSuccessStatusCode) {
        Write-Host "Request failed. Response body:" -ForegroundColor Red
        Write-Host $responseBody
        exit 1
    }

    try {
        $parsed = $responseBody | ConvertFrom-Json
        $parsed | ConvertTo-Json -Depth 12
    }
    catch {
        # Fallback if response is not valid JSON.
        Write-Host $responseBody
    }
}
finally {
    if ($multipartContent -ne $null) {
        foreach ($part in $multipartContent) {
            $part.Dispose()
        }
        $multipartContent.Dispose()
    }

    $httpClient.Dispose()
}
