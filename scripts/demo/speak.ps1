# Turns narration lines into WAV files using the speech voices built into Windows (no install, no internet).
# Called by record.mjs:  speak.ps1 -Json lines.json -OutDir folder [-Voice "Microsoft Zira Desktop"] [-Rate -1]
# Writes <key>.wav for every key in the JSON file. Rate runs from -10 (slowest) to 10; -1 is a touch slower than normal.
param(
  [Parameter(Mandatory = $true)][string]$Json,
  [Parameter(Mandatory = $true)][string]$OutDir,
  [string]$Voice = "",
  [int]$Rate = -1
)

Add-Type -AssemblyName System.Speech
$lines = Get-Content -Raw -Encoding UTF8 $Json | ConvertFrom-Json
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
if ($Voice) { $synth.SelectVoice($Voice) }
$synth.Rate = $Rate
$format = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(
  22050,
  [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen,
  [System.Speech.AudioFormat.AudioChannel]::Mono)

foreach ($line in $lines.PSObject.Properties) {
  $synth.SetOutputToWaveFile((Join-Path $OutDir ($line.Name + ".wav")), $format)
  $synth.Speak([string]$line.Value)
}
$synth.SetOutputToNull()
$synth.Dispose()
