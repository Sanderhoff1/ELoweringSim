param([string]$OutputPath='energy-preview.png')
Add-Type -AssemblyName System.Drawing
$data=Get-Content -LiteralPath 'docs/energy-canvas.json' -Raw | ConvertFrom-Json
$bitmap=New-Object System.Drawing.Bitmap(($data.width*2),($data.height*2))
$g=[System.Drawing.Graphics]::FromImage($bitmap)
$g.Clear([System.Drawing.ColorTranslator]::FromHtml('#101b2c'))
$g.ScaleTransform(2,2)
$g.SmoothingMode=[System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$g.TextRenderingHint=[System.Drawing.Text.TextRenderingHint]::AntiAlias
foreach($item in $data.items){
    $a=$item.coords
    $brush=New-Object System.Drawing.SolidBrush([System.Drawing.ColorTranslator]::FromHtml($(if($item.fill){$item.fill}else{'#101b2c'})))
    $pen=New-Object System.Drawing.Pen($brush.Color,[single]$(if($item.width){$item.width}else{1}))
    if($item.kind -eq 'text'){
        $size=[math]::Abs([int]($item.font -split ' ')[-1])
        $font=New-Object System.Drawing.Font('Segoe UI',$size,[System.Drawing.FontStyle]::Regular,[System.Drawing.GraphicsUnit]::Pixel)
        $format=[System.Drawing.StringFormat]::GenericTypographic.Clone()
        $format.Alignment=[System.Drawing.StringAlignment]::Center
        $rect=New-Object System.Drawing.RectangleF([single]($item.bbox[0]-4),[single]$item.bbox[1],[single]($item.bbox[2]-$item.bbox[0]+8),[single]($item.bbox[3]-$item.bbox[1]+5))
        $g.DrawString([string]$item.text,$font,$brush,$rect,$format)
        $g.Flush([System.Drawing.Drawing2D.FlushIntention]::Sync)
        $font.Dispose();$format.Dispose()
    }elseif($item.kind -eq 'line'){
        $pts=New-Object 'System.Collections.Generic.List[System.Drawing.PointF]'
        for($i=0;$i -lt $a.Count;$i+=2){$pts.Add((New-Object System.Drawing.PointF([single]$a[$i],[single]$a[$i+1])))}
        if($item.dash){$pen.DashStyle=[System.Drawing.Drawing2D.DashStyle]::Dash}
        if($item.arrow -eq 'last' -or $item.arrow -eq 'both'){$pen.CustomEndCap=New-Object System.Drawing.Drawing2D.AdjustableArrowCap(3,4)}
        if($item.arrow -eq 'both'){$pen.CustomStartCap=New-Object System.Drawing.Drawing2D.AdjustableArrowCap(3,4)}
        $g.DrawLines($pen,$pts.ToArray())
    }else{
        $rect=New-Object System.Drawing.RectangleF([single]$a[0],[single]$a[1],[single]($a[2]-$a[0]),[single]($a[3]-$a[1]))
        if($item.fill){if($item.kind -eq 'oval'){$g.FillEllipse($brush,$rect)}else{$g.FillRectangle($brush,$rect)}}
        if($item.outline){$pen.Color=[System.Drawing.ColorTranslator]::FromHtml($item.outline);if($item.kind -eq 'oval'){$g.DrawEllipse($pen,$rect)}else{$g.DrawRectangle($pen,$rect.X,$rect.Y,$rect.Width,$rect.Height)}}
    }
    $brush.Dispose();$pen.Dispose()
}
$bitmap.Save([System.IO.Path]::GetFullPath($OutputPath),[System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose();$bitmap.Dispose()
