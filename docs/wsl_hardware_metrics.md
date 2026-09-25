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

Unavailable measurements remain `NA` in `windows_metrics.json` for diagnostics, but their rows are omitted from the consolidated WSL `metrics.csv`. Valid zeros, including the NPU default `0.00`, are retained. Native Linux CSV behavior is unchanged.

GPU activity uses Windows counterparts of CCS/RCS/VCS/VECS/Copy, not identical Intel hardware counters. Processes are summed per physical engine; the busiest engine in each category is used, including the busiest decode/encode engine for Video. Measurements are host-wide and include unrelated Windows applications. Valid zero activity is distinct from an unavailable measurement.

## 1. Windows Host

In Windows PowerShell, check WSL and the installed GPU driver:

```powershell
wsl --version
wsl --list --verbose
Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion, PNPDeviceID
```

The target distribution must use WSL version 2. Use an up-to-date vendor-supported Windows GPU driver appropriate for the workload. Installing a Linux display driver inside WSL does not add Windows power sensors. Keep the already-working Docker/WSL GPU setup unchanged.

### Step 1: Install Windows Python

Install 64-bit Windows CPython, not just Python inside WSL. Python 3.11 is a reasonable starting point for the optional Python.NET integration. In **Windows PowerShell**, install it with Windows Package Manager:

```powershell
winget install --exact --id Python.Python.3.11 --source winget
```

If `winget` is unavailable, use an approved Windows Python installer from [python.org](https://www.python.org/downloads/windows/) or your organization's software portal. Include pip and the Python launcher in the installation. Follow organizational requirements for supported Python versions and updates.

Close and reopen PowerShell after installation. If Python is already installed, continue with the next step to verify it.

### Step 2: Find the Installed python.exe

In **Windows PowerShell**, run:

```powershell
py -3.11 -c "import sys; print(sys.executable)"
```

For example, the output might be:

```text
C:\Users\intel\AppData\Local\Programs\Python\Python311\python.exe
```

Use the path printed on your machine; the username and installation directory may differ. If the launcher is unavailable but `python` works, run:

```powershell
python -c "import sys; print(sys.executable)"
```

If this opens the Microsoft Store or reports that Python was not found, return to Step 1. The Store execution alias is not a usable Python installation.

### Step 3: Set WINDOWS_PYTHON

Switch to your **WSL terminal**. Convert the Windows path from Step 2 to a WSL path:

```bash
wslpath -u 'C:\Users\intel\AppData\Local\Programs\Python\Python311\python.exe'
```

For this example, the result is `/mnt/c/Users/intel/AppData/Local/Programs/Python/Python311/python.exe`. Set the shell variable to your converted path, keeping the quotes if it contains spaces:

```bash
export WINDOWS_PYTHON="/mnt/c/Users/intel/AppData/Local/Programs/Python/Python311/python.exe"
"$WINDOWS_PYTHON" -c "import os, sys; print(sys.executable, os.name); assert os.name == 'nt'"
```

The verification must print the installed executable and `nt`. Stop and correct the path if it fails.

For future Make invocations, set the same path in the root Makefile's existing assignment:

```makefile
WINDOWS_PYTHON ?= /mnt/c/Users/intel/AppData/Local/Programs/Python/Python311/python.exe
```

Alternatively, put `WINDOWS_PYTHON = /mnt/c/.../python.exe` with your full path in the root `.env` to keep machine-specific configuration out of the Makefile. Make assignments do not need surrounding quotes, even for paths containing spaces. Keep the existing `export WINDOWS_PYTHON` in the Makefile.

Make's export only affects its child processes; it does not set variables in your parent terminal. The shell `export` above is needed for manual commands in this guide and must be repeated in a new terminal. The collector uses the configured executable directly, with no interpreter discovery or launcher fallback. Use a WSL executable path or an executable name on WSL's `PATH`, not a Windows drive path or launcher arguments.

### Step 4: Configure Windows Pip's Proxy

If your network requires a proxy, find the existing settings in your **WSL terminal**:

```bash
printenv | grep -iE '^(http_proxy|https_proxy|all_proxy)='
```

Use the actual HTTP/HTTPS proxy URL reported for your network. For example, a value of `https_proxy=http://proxy.company.com:8080` identifies host `proxy.company.com` and port `8080`. Replace the placeholder below before running:

```bash
"$WINDOWS_PYTHON" -m pip config --user set global.proxy "http://YOUR_PROXY_HOST:PORT"
```

This writes Windows pip's user configuration, normally `%APPDATA%\pip\pip.ini`. It is a one-time setting for that Windows user and interpreter configuration; no proxy command needs to be added to the Makefile. Docker and Linux pip proxy settings do not necessarily configure Windows pip. The proxy must be reachable from Windows, not only from WSL.

If no proxy is listed, check **Windows Settings > Network & internet > Proxy**, or ask IT for the approved proxy endpoint or Python package mirror. A PAC setup-script URL is not a proxy endpoint that pip can use directly. Do not guess a proxy, and do not store proxy credentials in shell history or repository files. Skip proxy configuration when your network permits direct access.

### Step 5: Install Dependencies and Verify

In the same **WSL terminal**, install packages into Windows Python:

```bash
"$WINDOWS_PYTHON" -m pip install --timeout 60 psutil pywin32
"$WINDOWS_PYTHON" -c "import psutil, win32pdh; print('Windows dependencies OK')"
```

After both commands succeed, run from the loss-prevention repository root:

```bash
make build-benchmark WSL2=true
```

In WSL mode, this target verifies the configured Windows interpreter and installs `psutil pywin32`, using Windows pip's saved proxy configuration. It does not locate or install Python itself. Optional power dependencies are not installed automatically.

Saving proxy configuration does not prove connectivity. If installation fails, inspect the error for proxy connection, authentication, or certificate failures. Connection timeouts can lead to misleading "No matching distribution found" messages. For certificate failures, use your organization's approved CA configuration rather than disabling TLS verification.

### Verify GPU Counters

For an English Windows installation, inspect counters in PowerShell while a GPU workload is active:

```powershell
Get-Counter '\GPU Engine(*)\Utilization Percentage' -SampleInterval 1 -MaxSamples 3
```

PowerShell counter names can be localized. The collector uses `AddEnglishCounter` to resolve the localized path. No engine instances while idle is not proof of a broken driver; check under load. Confirm that the WSL workload is visible in these counters on the actual host.

## 2. WSL and Shared Output Access

From the repository root in WSL:

```bash
uname -r
command -v wslpath
python3 --version
python3 -m venv --help
docker info
docker compose version
mkdir -p benchmark
"$WINDOWS_PYTHON" -c "import os, sys; p=sys.argv[1]; print(p); assert os.path.isdir(p); assert os.access(p, os.W_OK)" "$(wslpath -w "$PWD/benchmark")"
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
"$WINDOWS_PYTHON" -m pip install pythonnet
"$WINDOWS_PYTHON" -c "import clr; print('Python.NET import OK')"
export WINDOWS_LHM_DLL='C:\Tools\LibreHardwareMonitor\LibreHardwareMonitorLib.dll'
```

Use a library build compatible with the installed .NET runtime and Python.NET (the .NET Framework build uses the Windows CLR). Do not install the unrelated package named `clr`. If assembly loading fails, check the complete release contents, required .NET runtime, architecture, and Windows file-blocking/driver diagnostics. Do not assume a newer release has identical driver support.

One-time sensor discovery, from the repository root in WSL:

```bash
mkdir -p benchmark
"$WINDOWS_PYTHON" "$(wslpath -w "$PWD/performance-tools/benchmark-scripts/windows_metrics.py")" \
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