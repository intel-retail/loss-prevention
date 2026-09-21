# WSL Benchmark Hardware Metrics: Prerequisites and Operation

For initial environment installation, see [WSL setup](wsl2_setup.md).
For a concise description of automatic collection and report fields, see
[WSL benchmark metrics](wsl2_benchmark.md).

## Scope and Portability

Run the benchmark from the loss-prevention repository root inside WSL2. The project flag is `WSL2=true`, not `WSL=true`. The Makefile detects a Microsoft kernel automatically; pass the flag explicitly when validating this setup. Windows collection is disabled for `WSL2=false`.

No source edits should be needed on another supported host. Installed executable paths, hardware sensors, permissions, and adapter identifiers are host-specific. Sensor and adapter identifiers must be rechecked after reboot, driver changes, or GPU changes. This is not a guarantee that every WSL machine can supply every measurement.

| Measurement | Windows requirement | When unavailable |
| --- | --- | --- |
| GPU activity | Windows GPU driver exposing GPU Engine PDH counters; Windows Python and pywin32 | `NA` |
| GPU power | Optional Libre Hardware Monitor library, Python.NET, working GPU power sensor, explicit sensor/adapter selection | `NA` |
| CPU package power and DRAM bandwidth | Native Intel PCM, supported Intel CPU/counters, working driver and permissions | `NA` |
| NPU | No collector required; intentional WSL reporting default | `0.00` |

GPU activity uses Windows counterparts of CCS/RCS/VCS/VECS/Copy, not identical Intel hardware counters. Processes are summed per physical engine; the busiest engine in each category is used, including the busiest decode/encode engine for Video. Measurements are host-wide and include unrelated Windows applications. Valid zero activity is distinct from an unavailable measurement.

## 1. Windows Host

In Windows PowerShell, check WSL and the installed GPU driver:

```powershell
wsl --version
wsl --list --verbose
Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion, PNPDeviceID
```

The target distribution must use WSL version 2. Use an up-to-date vendor-supported Windows GPU driver appropriate for the workload. Installing a Linux display driver inside WSL does not add Windows power sensors. Keep the already-working Docker/WSL GPU setup unchanged.

Install 64-bit Windows CPython (Python 3.11 is a reasonable starting point for Python.NET compatibility). Make `python.exe` accessible from WSL; do not rely on the Microsoft Store execution alias. In WSL, verify that it is actually Windows Python:

```bash
python.exe -c "import os, sys; print(sys.executable, os.name); assert os.name == 'nt'"
python.exe -m pip install pywin32
python.exe -c "import win32pdh; print('PDH import OK')"
```

The current `make build-benchmark WSL2=true` also invokes `python.exe` and installs `psutil pywin32`. Therefore `python.exe` must be available even if `WINDOWS_PYTHON` selects a different interpreter for the collector. Install collector dependencies into the selected interpreter. Optional power dependencies are not installed automatically.

For an English Windows installation, inspect counters in PowerShell while a GPU workload is active:

```powershell
Get-Counter '\GPU Engine(*)\Utilization Percentage' -SampleInterval 1 -MaxSamples 3
```

PowerShell counter names can be localized. The collector uses `AddEnglishCounter` to resolve the localized path. No engine instances while idle is not proof of a broken driver; check under load. Confirm that the WSL workload is visible in these counters on the actual host.

## 2. WSL and Shared Output Access

From the repository root in WSL:

```bash
uname -r
command -v python.exe wslpath
python3 --version
python3 -m venv --help
docker info
docker compose version
mkdir -p benchmark
python.exe -c "import os, sys; p=sys.argv[1]; print(p); assert os.path.isdir(p); assert os.access(p, os.W_OK)" "$(wslpath -w "$PWD/benchmark")"
```

Windows interoperability must be enabled. The Windows process must be able to read the helper through its `wslpath -w` path and write the results directory, including when it is a `\\wsl.localhost\...` share. Linux `sudo` does not grant Windows Administrator privileges. If required by a telemetry driver, start Windows Terminal as Administrator and enter the WSL distribution from there; verify access in that context. Do not disable Windows security features to force an unsupported driver to load.

Keep the existing model, video, workload mapping, container registry, and GPU-runtime prerequisites used by your working benchmark. These telemetry changes do not provision the workload itself.

## 3. Optional Native Windows PCM

Obtain Intel PCM from the [official project](https://github.com/intel/pcm) and follow its Windows build/driver requirements. A Linux `pcm` binary is not sufficient. Keep the executable and its required Windows driver/runtime files together.

In Windows PowerShell, test the native binary from its installation folder:

```powershell
Set-Location C:\Tools\pcm
.\pcm.exe 1 -i=3 -nc
```

The example path is a placeholder. Check for real package energy and memory READ/WRITE measurements, not driver errors or unsupported-counter messages. Some CPUs, virtualized security configurations, or drivers do not expose these counters. PCM support is Intel/platform-specific and is not available on every Windows host.

In the WSL shell used for benchmarking, select the installed Windows executable:

```bash
export WINDOWS_PCM_EXE='C:\Tools\pcm\pcm.exe'
```

If omitted, the Windows worker searches its Windows PATH for `pcm.exe`. The worker starts PCM automatically after warm-up and writes its CSV-formatted raw output to `benchmark/windows_pcm_raw.log`; no manually running PCM process is required during benchmarking. Package energy is divided by elapsed sample time to obtain watts. READ+WRITE GB/s is converted to MB/s. The first PCM sample is discarded because its preceding timestamp is unavailable.

## 4. Optional GPU Power

Use the [official Libre Hardware Monitor release](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases) or a trusted build. Extract the complete distribution, not just the DLL; retain companion assemblies and driver files. The implementation uses the library's `Computer`, `Hardware`, and typed `Power` sensor API, not WMI values that may hide missing readings. Library/runtime and hardware compatibility must be validated on the target host.

Install Python.NET into the Windows interpreter used by the collector:

```bash
python.exe -m pip install pythonnet
python.exe -c "import clr; print('Python.NET import OK')"
export WINDOWS_LHM_DLL='C:\Tools\LibreHardwareMonitor\LibreHardwareMonitorLib.dll'
```

Use a library build compatible with the installed .NET runtime and Python.NET (the .NET Framework build uses the Windows CLR). Do not install the unrelated package named `clr`. If assembly loading fails, check the complete release contents, required .NET runtime, architecture, and Windows file-blocking/driver diagnostics. Do not assume a newer release has identical driver support.

One-time sensor discovery, from the repository root in WSL:

```bash
mkdir -p benchmark
python.exe "$(wslpath -w "$PWD/performance-tools/benchmark-scripts/windows_metrics.py")" \
  --output-dir "$(wslpath -w "$PWD/benchmark")" \
  --lhm-dll "$WINDOWS_LHM_DLL" --list-gpu-power-sensors
```

This writes `benchmark/windows_gpu_power_sensors.json` and prints the GPU hardware names, sensor identifiers, and readings. A null value means unavailable. Only `Power` sensors attached to GPU hardware are eligible; CPU package sensors are excluded. Select the sensor representing the intended GPU power domain, not a GPU rail or subcomponent if you need total GPU power. Not every GPU exposes a suitable total-power sensor. An empty list or persistent null values means this provider cannot supply that measurement with the current hardware/driver/permissions.

Configure the exact identifiers found on this machine:

```bash
export WINDOWS_GPU_POWER_SENSOR='<sensor_id from windows_gpu_power_sensors.json>'
export WINDOWS_GPU_POWER_ADAPTER='<luid_..._phys_... for the same physical GPU>'
```

Obtain the PDH adapter identifier from GPU Engine counter instance names or the `adapters` object in `benchmark/windows_metrics.json` after an initial benchmark without GPU-power settings. Verify that it is the same physical GPU as the selected Libre Hardware Monitor sensor. On multi-GPU machines, do not guess from enumeration order: use Windows adapter diagnostics to resolve the LUID, or leave GPU power unconfigured if the association is uncertain. LUIDs can change after reboot. The configured power adapter is assigned `GPU_1`; other observed adapters receive subsequent numbers. These numbers need not match Task Manager or Linux qmassa numbering.

The discovery command is setup only. During benchmarking the collector opens the library, updates sensors, and closes it automatically. The Libre Hardware Monitor GUI does not need to run. Missing samples are skipped; if no valid reading exists, GPU watts remain `NA`. No CPU-package-to-GPU substitution is performed. Driver contention with PCM is possible and must be checked on the target machine.

## 5. Run and Check Results

Run in the same WSL shell as the optional exports:

```bash
make benchmark WSL2=true
make consolidate-metrics WSL2=true
```

The ordinary benchmark target does not automatically invoke consolidation; `benchmark-quickstart` does. The existing benchmark and stream-density Compose lifecycle starts and stops the Windows worker automatically. It begins sampling after the configured warm-up. Stream-density iterations replace telemetry with the latest collected run rather than accumulating all iterations. Auxiliary Compose starts through the same helper also trigger collection; there is no archive or automatic best-iteration selection. The regular `run-lp` target does not launch this benchmark collector. The existing plotting command has no new integration for the Windows hardware summary.

By default all generated telemetry files are under the repository's `benchmark` directory:

```text
windows_metrics.json          Final summary, sources and adapter mapping
windows_metrics.log           Worker warnings and errors
windows_pcm_raw.log           PCM CSV-formatted samples, when available
windows_pcm.log               PCM stdout/stderr, when launched
windows_gpu_power_sensors.json  Optional one-time sensor discovery
metrics.csv                  Produced by consolidation
```

If you override `RESULTS_DIR`, pass the same absolute directory to benchmark and consolidation. Outputs then go there intentionally; there is no random output directory. Telemetry from a preceding run is reset. Worker failure does not stop the workload; inspect logs when fields remain `NA`. The existing Makefile dependency-install step can still fail if Windows Python or network access is missing, so complete prerequisites before benchmarking.

Do not treat presence of rows as proof of successful collection. Check that adapter metadata matches the intended GPU, GPU activity changes under load, power readings are plausible for that device, PCM logs contain no permission/unsupported-counter errors, and NPU is exactly the intentional `0.00` default. Close unrelated GPU-heavy applications for repeatable host-wide measurements.

## Validation Status

Linux-side tests cover WSL guards, native-Linux no-op behavior, GPU aggregation, optional power sensor filtering, missing-value handling, PCM unit conversion, and mocked lifecycle failures. They do not validate Windows driver access, actual sensor accuracy, concurrent PCM/library operation, or WSL interoperability. Those checks must be performed on the destination Windows machine before relying on the measurements.