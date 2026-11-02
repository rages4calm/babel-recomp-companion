param([string]$ArtworkRoot = $PSScriptRoot)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$ArtworkRoot = (Resolve-Path -LiteralPath $ArtworkRoot).Path
$sizes = @(16,20,24,32,40,48,64,128,256)
foreach ($stem in @('gaia-game','gaia-launcher')) {
    $source = Join-Path $ArtworkRoot ($stem + '.png')
    $destination = Join-Path $ArtworkRoot ($stem + '.ico')
    $image = [System.Drawing.Bitmap]::new($source)
    $frames = [System.Collections.Generic.List[byte[]]]::new()
    try {
        if ($image.Width -ne $image.Height) { throw 'Artwork must be square; this converter never crops or stretches it.' }
        if ($image.GetPixel(0,0).A -ne 0) { throw 'Expected transparent source artwork.' }
        foreach ($size in $sizes) {
            $bitmap = [System.Drawing.Bitmap]::new($size, $size, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
            $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
            $stream = [System.IO.MemoryStream]::new()
            try {
                $graphics.CompositingMode = [System.Drawing.Drawing2D.CompositingMode]::SourceCopy
                $graphics.CompositingQuality = [System.Drawing.Drawing2D.CompositingQuality]::HighQuality
                $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
                $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
                $graphics.Clear([System.Drawing.Color]::Transparent)
                $graphics.DrawImage($image, [System.Drawing.Rectangle]::new(0,0,$size,$size), 0,0,$image.Width,$image.Height,[System.Drawing.GraphicsUnit]::Pixel)
                $bitmap.Save($stream, [System.Drawing.Imaging.ImageFormat]::Png)
                $frames.Add($stream.ToArray())
            } finally { $graphics.Dispose(); $bitmap.Dispose(); $stream.Dispose() }
        }
    } finally { $image.Dispose() }
    $output = [System.IO.MemoryStream]::new()
    $writer = [System.IO.BinaryWriter]::new($output)
    try {
        $writer.Write([uint16]0); $writer.Write([uint16]1); $writer.Write([uint16]$sizes.Count)
        $offset = 6 + 16 * $sizes.Count
        for ($i = 0; $i -lt $sizes.Count; $i++) {
            $dimension = if ($sizes[$i] -eq 256) { 0 } else { $sizes[$i] }
            $writer.Write([byte]$dimension); $writer.Write([byte]$dimension)
            $writer.Write([byte]0); $writer.Write([byte]0)
            $writer.Write([uint16]1); $writer.Write([uint16]32)
            $writer.Write([uint32]$frames[$i].Length); $writer.Write([uint32]$offset)
            $offset += $frames[$i].Length
        }
        foreach ($frame in $frames) { $writer.Write([byte[]]$frame) }
        $writer.Flush()
        [System.IO.File]::WriteAllBytes($destination, $output.ToArray())
    } finally { $writer.Dispose(); $output.Dispose() }
    [pscustomobject]@{Icon=$destination;Sizes=$sizes;Frames=$frames.Count;Sha256=(Get-FileHash -Algorithm SHA256 -LiteralPath $destination).Hash.ToLowerInvariant()}
}
