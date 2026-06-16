# OmniAnomaly 答辩 PPT 生成脚本
# 需要: Microsoft PowerPoint 已安装

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

$baseDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$imagesDir = Join-Path $baseDir "images"

# ── 启动 PowerPoint ──
$ppt = New-Object -ComObject PowerPoint.Application
$pres = $ppt.Presentations.Add()
$pres.PageSetup.SlideWidth  = 960   # 16:9 宽屏
$pres.PageSetup.SlideHeight = 540

# ── 辅助函数 ──
function New-Slide($title, $layout=1) {
    # layout: 1=标题页, 2=标题+内容
    $slide = $pres.Slides.Add($pres.Slides.Count + 1, 12)  # 12 = ppLayoutBlank
    return $slide
}

function Add-TextBox($slide, $left, $top, $width, $height, $text, $fontSize=14, $bold=$false, $color=[System.Drawing.Color]::FromArgb(0x33,0x33,0x33)) {
    $shape = $slide.Shapes.AddTextbox(1, $left, $top, $width, $height)  # 1 = msoTextOrientationHorizontal
    $shape.TextFrame.TextRange.Text = $text
    $shape.TextFrame.TextRange.Font.Size = $fontSize
    $shape.TextFrame.TextRange.Font.Bold = $bold
    $shape.TextFrame.TextRange.Font.Color.RGB = ($color.B + $color.G * 256 + $color.R * 65536)
    $shape.TextFrame.TextRange.ParagraphFormat.Alignment = 2  # ppAlignLeft
    $shape.Fill.Visible = $false
    $shape.Line.Visible = $false
    $shape.TextFrame.WordWrap = $true
    return $shape
}

function Add-Title($slide, $text) {
    # 页面标题栏
    $bar = $slide.Shapes.AddShape(1, 0, 0, 960, 60)  # 顶部色条
    $bar.Fill.ForeColor.RGB = 0x1A4876
    $bar.Line.Visible = $false
    Add-TextBox $slide 40 12 880 48 $text 28 $true ([System.Drawing.Color]::White)
}

function Add-Image($slide, $file, $left, $top, $width, $height) {
    $path = Join-Path $imagesDir $file
    if (Test-Path $path) {
        return $slide.Shapes.AddPicture($path, $false, $true, $left, $top, $width, $height)
    } else {
        Write-Host "⚠ 图片不存在: $path" -ForegroundColor Yellow
        return $null
    }
}

function Add-Table($slide, $data, $left, $top, $colWidths) {
    # $data = @( @("h1","h2"), @("v1","v2"), ... )
    $rows = $data.Count
    $cols = $data[0].Count
    $totalWidth = 0
    foreach ($w in $colWidths) { $totalWidth += $w }

    $table = $slide.Shapes.AddTable($rows, $cols, $left, $top, $totalWidth, 20 * $rows)
    for ($r=0; $r -lt $rows; $r++) {
        for ($c=0; $c -lt $cols; $c++) {
            $cell = $table.Table.Cell($r+1, $c+1)
            $cell.Shape.TextFrame.TextRange.Text = $data[$r][$c]
            $cell.Shape.TextFrame.TextRange.Font.Size = 11
            if ($r -eq 0) {
                $cell.Shape.TextFrame.TextRange.Font.Bold = $true
                $cell.Shape.Fill.ForeColor.RGB = 0x1A4876
                $cell.Shape.TextFrame.TextRange.Font.Color.RGB = 0xFFFFFF
            }
        }
    }
    return $table
}

# ═══════════════════════════════════════
# 第 1 页 — 标题页
# ═══════════════════════════════════════
$s = New-Slide
$grad = $s.Shapes.AddShape(1, 0, 0, 960, 540)
$grad.Fill.ForeColor.RGB = 0x1A4876
$grad.Line.Visible = $false
Add-TextBox $s 80 130 800 80 "OmniAnomaly 论文复现" 42 $true ([System.Drawing.Color]::White)
Add-TextBox $s 80 210 800 50 "Robust Anomaly Detection for Multivariate Time Series (KDD 2019)" 18 $false ([System.Drawing.Color]::FromArgb(0xCC,0xCC,0xCC))
Add-TextBox $s 80 290 800 40 "Online Boutique 微服务系统 — Kubernetes + Prometheus + ChaosMesh" 16 $false ([System.Drawing.Color]::FromArgb(0xAA,0xAA,0xAA))
# 分隔线
$line = $s.Shapes.AddShape(1, 80, 350, 300, 3)
$line.Fill.ForeColor.RGB = 0xFFCC00
$line.Line.Visible = $false
Add-TextBox $s 80 380 300 30 "答辩人：tamotasmash" 14 $false ([System.Drawing.Color]::FromArgb(0xCC,0xCC,0xCC))
Add-TextBox $s 80 410 400 30 "分支：release/v0.10.2" 14 $false ([System.Drawing.Color]::FromArgb(0xCC,0xCC,0xCC))

# ═══════════════════════════════════════
# 第 2 页 — 问题定义
# ═══════════════════════════════════════
$s = New-Slide
Add-Title $s "问题定义：多元时间序列异常检测"

Add-TextBox $s 40 80 280 30 "场景" 14 $true
Add-TextBox $s 40 105 400 60 "Online Boutique 微服务系统`n11 个服务，Kubernetes + Prometheus 监控" 12 $false

Add-TextBox $s 40 180 280 30 "输入" 14 $true
Add-TextBox $s 40 205 400 40 "22 维时间序列（11 服务 × {cpu, mem}），每 30 秒一个采样点" 12 $false

Add-TextBox $s 40 260 280 30 "输出" 14 $true
Add-TextBox $s 40 285 400 40 "每个时间窗口的异常分数 + 阈值判定（正常/异常）" 12 $false

Add-TextBox $s 40 340 280 30 "故障类型" 14 $true
Add-TextBox $s 40 365 400 80 "• CPU Stress (2核, 80%负载)`n• Network Delay (500ms + 100ms jitter)`n• Pod Kill" 12 $false

# 实验矩阵
$tbl = @(
    @("故障类型", "目标服务", "参数"),
    @("CPU Stress", "frontend / cart / productcatalog", "2核, 80%"),
    @("Network Delay", "frontend / cart / productcatalog", "500ms + 100ms"),
    @("Pod Kill", "frontend / cart / productcatalog", "pod-kill action")
)
Add-Table $s $tbl 500 100 @(130, 200, 130)

# ═══════════════════════════════════════
# 第 3 页 — 核心思想：重建概率 vs 重建误差
# ═══════════════════════════════════════
$s = New-Slide
Add-Title $s "核心创新：从重建误差到重建概率"

# 左侧：传统方法
$box1 = $s.Shapes.AddShape(5, 30, 90, 430, 190)  # 圆角矩形
$box1.Fill.ForeColor.RGB = 0xFFE0E0
$box1.Line.ForeColor.RGB = 0xCC0000
Add-TextBox $s 50 95 200 30 "✘ 传统方法（重建误差）" 14 $true ([System.Drawing.Color]::FromArgb(0xCC,0,0))
Add-TextBox $s 60 130 380 130 "x → Encoder → z → Decoder → x̂`n`n异常判定: MSE(x, x̂) > 阈值`n`n问题: 各维度阈值难统一`n     无法表达不确定性" 11 $false

# 右侧：OmniAnomaly
$box2 = $s.Shapes.AddShape(5, 490, 90, 440, 190)
$box2.Fill.ForeColor.RGB = 0xE0FFE0
$box2.Line.ForeColor.RGB = 0x009900
Add-TextBox $s 510 95 200 30 "✔ OmniAnomaly（重建概率）" 14 $true ([System.Drawing.Color]::FromArgb(0,0x99,0))
Add-TextBox $s 520 130 380 130 "x → Encoder → q(z|x) → Decoder → p(x|z)`n`n异常判定: E[log p(x|z)] < 阈值`n`n优势: 概率天然可比`n     包含重建的不确定性" 11 $false

# 底部总结
Add-TextBox $s 40 310 880 60 '核心直觉：模型只在正常数据上训练，学会了正常数据的"形状"。异常数据进来时，模型试图用正常的"形状"去解释它，`n结果自然是概率极低——这就是检测的依据。' 14 $true ([System.Drawing.Color]::FromArgb(0x1A,0x48,0x76))

Add-TextBox $s 40 380 880 50 "异常分数 = −E_q(z|x)[log p(x|z)]  ——  不需要手工设定维度权重，一个公式统一 22 维" 12 $false

# ═══════════════════════════════════════
# 第 4 页 — 四大核心组件
# ═══════════════════════════════════════
$s = New-Slide
Add-Title $s "模型架构：四大核心组件"

$comps = @(
    @{name="GRU 循环网络"; role="捕捉时序依赖"; why="CPU飙高后内存通常会跟着变——GRU捕捉这种先后关系"; cfg="hidden=128"},
    @{name='VAE 变分自编码器'; role='学习正常分布'; why='输出分布而非点估计，能表达"这个地方我不确定"'; cfg='z_dim=6'},
    @{name='Planar Normalizing Flow'; role='增强后验表达力'; why='标准VAE假设后验是高斯——太简单，NF把高斯"揉"成任意形状'; cfg='layers=10'},
    @{name="Linear Gaussian SSM"; role="连接时间步"; why="标准VAE假设z_t独立，但真实系统状态连续演化：z_t=z_{t-1}+ε"; cfg="启用"}
)

$y = 80
foreach ($comp in $comps) {
    $idx = [array]::IndexOf($comps, $comp) + 1
    $arrow = if ($idx -lt 4) { "  →" } else { "" }
    $txt = "[$idx] $($comp.name)$arrow"
    Add-TextBox $s 40 $y 250 28 $txt 14 $true ([System.Drawing.Color]::FromArgb(0x1A,0x48,0x76))
    Add-TextBox $s 300 $y 150 28 "作用: $($comp.role)" 11 $false
    Add-TextBox $s 460 $y 300 28 "为什么: $($comp.why)" 11 $false
    Add-TextBox $s 780 $y 150 28 "配置: $($comp.cfg)" 11 $false ([System.Drawing.Color]::FromArgb(0x88,0x88,0x88))
    $y += 40
}

# 流程图
Add-TextBox $s 40 ($y+20) 880 80 "数据流: x_t−w+1…x_t  →  [GRU编码]  →  q(z|x)  →  [Planar NF]  →  LGSSM(z_t|z_t−1)  →  [GRU解码]  →  p(x|z)  →  异常分数" 13 $true
Add-TextBox $s 40 ($y+80) 880 60 "每个窗口采样 1024 个 z 估计 E[log p(x|z)]；仅评估窗口最后一个点的分数（last_point_only = True）" 11 $false ([System.Drawing.Color]::FromArgb(0x88,0x88,0x88))

# ═══════════════════════════════════════
# 第 5 页 — 9 组实验总览（核心页）
# ═══════════════════════════════════════
$s = New-Slide
Add-Title $s "9 组对照实验：从 F1=0.112 到 F1=0.786"
Add-Image $s "fig1_experiments_comparison.png" 20 65 920 410

# 底部关键数字
Add-TextBox $s 30 490 300 40 "#1→#3: F1 0.112→0.553 (+392%)`n故障强度比特征工程重要" 11 $true ([System.Drawing.Color]::FromArgb(0xCC,0,0))
Add-TextBox $s 340 490 300 40 "#5→#6: F1 0.589→0.968 (+64%)`n数据质量决定天花板" 11 $true ([System.Drawing.Color]::FromArgb(0,0x99,0))
Add-TextBox $s 650 490 290 40 "#1→#9: F1 0.112→0.786 (+602%)`n整体优化路径有效" 11 $true ([System.Drawing.Color]::FromArgb(0x1A,0x48,0x76))

# ═══════════════════════════════════════
# 第 6 页 — 维度 vs F1
# ═══════════════════════════════════════
$s = New-Slide
Add-Title $s "降维：F1 提升 7 倍的关键杠杆"
Add-Image $s "fig2_dimension_vs_f1.png" 50 65 600 400

Add-TextBox $s 680 80 250 30 "核心发现" 14 $true
Add-TextBox $s 680 110 250 200 "• 494维 → 22维`n  F1 提升 7 倍`n`n• 人工精选 22维`n  远超自动筛选 36-54维`n`n• 92.6% 的列零方差`n  这些不是特征，是噪声`n`n• 只取 boutique 命名空间`n  只取 cpu + memory" 11 $false

Add-TextBox $s 40 480 880 40 "关键启示：花 80% 的精力在数据上。降维是最廉价的提升手段——从 494 列删到 22 列不需要任何算法改动。" 13 $true ([System.Drawing.Color]::FromArgb(0x1A,0x48,0x76))

# ═══════════════════════════════════════
# 第 7 页 — 异常分数可视化
# ═══════════════════════════════════════
$s = New-Slide
Add-Title $s "实验 #9 检测效果可视化 (F1=0.786)"
Add-Image $s "fig3_score_distribution.png" 20 65 460 220
Add-Image $s "fig4_score_timeline.png" 20 295 920 235

Add-TextBox $s 500 80 440 60 "分布图：异常窗口（红色）与正常窗口（蓝色）`n的异常分数分布——两组重心明显分离" 10 $false
Add-TextBox $s 500 140 440 60 "时序图：红色背景 = 故障注入时段。每次注入后`n异常分数立即攀升，清除后回落" 10 $false

# ═══════════════════════════════════════
# 第 8 页 — 窗口长度分析
# ═══════════════════════════════════════
$s = New-Slide
Add-Title $s "超参数分析：窗口长度 & POT 失效"
Add-Image $s "fig5_window_sweep.png" 30 65 500 400

Add-TextBox $s 560 80 370 30 "论文默认 vs 真实最优" 14 $true
$tbl2 = @(
    @("窗口", "F1", "说明"),
    @("w5", "0.600", "论文默认，最差"),
    @("w10", "0.616", ""),
    @("w20", "0.643", ""),
    @("w28", "0.692", ""),
    @("w30", "0.786 ★", "真实数据最优"),
    @("w40", "0.762", "过大→衰减")
)
Add-Table $s $tbl2 560 115 @(60, 80, 150)

Add-TextBox $s 560 290 370 120 "关键发现：`n• 论文 w5 在真实数据上低 18.6pp`n• 真实故障是渐进的，需要大窗口捕捉累积偏差`n• 窗口过长 (w40) 开始丢失局部信息" 12 $false

Add-TextBox $s 560 420 370 100 "POT 失效：`n• level=0.01 → TP=0（全判正常）`n• level 调大一档 → FP 爆炸`n• 637 行训练集太小，极值理论无法拟合`n• 最终 F1 依赖 Best-F1 搜索（需要真实标签）" 11 $false ([System.Drawing.Color]::FromArgb(0xCC,0x44,0))

# ═══════════════════════════════════════
# 第 9 页 — 核心结论
# ═══════════════════════════════════════
$s = New-Slide
Add-Title $s "核心结论与局限讨论"

# 左边：四个发现
Add-TextBox $s 30 80 500 28 "四个核心发现" 16 $true ([System.Drawing.Color]::FromArgb(0x1A,0x48,0x76))

$findings = @(
    @{num="1"; title="数据质量 > 模型调参"; evid="最大三次跳升来自增强故障、换数据、重新采集"},
    @{num="2"; title="降维是关键杠杆"; evid="494维→22维，F1×7，人工精选>自动筛选"},
    @{num="3"; title="故障强度至关重要"; evid="1核→2核，F1×5，弱信号检测仍是难题"},
    @{num="4"; title="POT在小样本不可靠"; evid="637行上完全失效，需更大数据集"}
)

$y = 120
foreach ($f in $findings) {
    Add-TextBox $s 45 $y 30 24 "▶" 14 $true ([System.Drawing.Color]::FromArgb(0xFF,0xCC,0))
    Add-TextBox $s 75 $y 150 24 "$($f.title)" 12 $true
    Add-TextBox $s 230 $y 270 24 "$($f.evid)" 10 $false
    $y += 42
}

# 右边：局限性
Add-TextBox $s 560 80 370 28 "局限性" 16 $true ([System.Drawing.Color]::FromArgb(0xCC,0x44,0))

$limits = @(
    "训练集仅 637 行（~6h），远少于论文数万条",
    "仅 cpu/mem 特征，缺少网络/磁盘/应用级指标",
    "仅 3 种故障类型，未覆盖内存泄漏、级联故障",
    "单故障假设，生产环境常为多故障并发",
    "POT 完全失效，依赖 Best-F1（需真实标签）",
    "TensorFlow 1.x (EOL)，迁移成本高"
)
$y = 115
foreach ($lim in $limits) {
    Add-TextBox $s 580 $y 350 22 "• $lim" 10 $false
    $y += 30
}

# 底部：后续工作
Add-TextBox $s 40 430 880 40 "后续：延长训练集(12-24h) → 扩展指标(网络/磁盘) → 丰富故障类型 → 模型升级 TF2/PyTorch → 接入 aiopsagent LangGraph 管道" 10 $false ([System.Drawing.Color]::FromArgb(0x88,0x88,0x88))

# 致谢
Add-TextBox $s 40 480 880 40 "谢谢！欢迎提问" 28 $true ([System.Drawing.Color]::FromArgb(0x1A,0x48,0x76))

# ═══════════════════════════════════════
# 保存
# ═══════════════════════════════════════
$output = Join-Path $baseDir "OmniAnomaly_答辩PPT.pptx"
$slideCount = $pres.Slides.Count
$pres.SaveAs($output)
$pres.Close()
$ppt.Quit()

Write-Host ""
Write-Host "✅ PPT 已生成: $output" -ForegroundColor Green
Write-Host "   共 $slideCount 页" -ForegroundColor Green

# 释放 COM 对象
[System.Runtime.Interopservices.Marshal]::ReleaseComObject($pres) | Out-Null
[System.Runtime.Interopservices.Marshal]::ReleaseComObject($ppt) | Out-Null
[System.GC]::Collect()
[System.GC]::WaitForPendingFinalizers()
