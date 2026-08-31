# Running Loss Prevention on Windows 11 + WSL2

This guide takes a clean Windows 11 machine to a working Loss Prevention environment
under WSL2. It is written for someone who has never used WSL before.

Follow the steps **in order**. Several of them fail in confusing ways if done out of
sequence — particularly the proxy configuration, which must come before any download.

---

## Contents

1. [BIOS virtualization](#1-bios-virtualization)
2. [Install WSL2 and Ubuntu 24.04](#2-install-wsl2-and-ubuntu-2404)
3. [Proxy configuration](#3-proxy-configuration)
4. [Base packages](#4-base-packages)
5. [Enable systemd](#5-enable-systemd)
6. [Install Docker Engine](#6-install-docker-engine)
7. [Docker daemon proxy](#7-docker-daemon-proxy)
8. [Docker build-time proxy](#8-docker-build-time-proxy)
9. [Memory and CPU tuning](#9-memory-and-cpu-tuning)
10. [Clone the repository](#10-clone-the-repository)
11. [GPU and NPU verification](#11-gpu-and-npu-verification)
12. [Smoke test](#12-smoke-test)
13. [Troubleshooting](#troubleshooting)

---

## Conventions

Commands are labelled by where they run:

| Label | Where |
|---|---|
| **PowerShell** | Windows PowerShell or Terminal, on the Windows side |
| **Ubuntu** | Inside the WSL2 Ubuntu distro |

Getting these mixed up is the single most common early mistake.

---

## 1. BIOS virtualization

WSL2 is a lightweight virtual machine, so hardware virtualization must be enabled.

**PowerShell** — check whether a hypervisor is already active:

```powershell
systeminfo | findstr /i "Hyper-V"
```

Expected:

```text
Hyper-V Requirements:   A hypervisor has been detected.
                        Features required for Hyper-V will not be displayed.
```

That message means virtualization is **already on**. If instead you see a list of
requirements with `No` values, reboot into BIOS/UEFI and enable
*Intel Virtualization Technology (VT-x)*.

Enable the Windows feature:

```powershell
wsl.exe --install --no-distribution
```

Reboot, then confirm:

```powershell
dism /online /get-featureinfo /featurename:VirtualMachinePlatform
```

Expected: `State : Enabled`.

Finally, ask WSL itself whether the platform is usable:

```powershell
wsl --status
```

Expected output on a working machine:

```text
Default Distribution: Ubuntu-24.04
Default Version: 2
```

If virtualization is still disabled, this command reports it explicitly — for example
`WSL2 is not supported with your current machine configuration` or a prompt to enable
the *Virtual Machine Platform* optional component. That message is the clearest
confirmation that step 1 is incomplete; go back to BIOS before continuing.

---

## 2. Install WSL2 and Ubuntu 24.04

**PowerShell:**

```powershell
wsl --set-default-version 2
wsl --list --online
wsl --install -d Ubuntu-24.04
```

The installer prompts for a **Linux username and password**. These are independent of
your Windows account. Remember the password — it is your `sudo` password.

Record your version baseline:

```powershell
wsl --version
wsl -l -v
```

Example output:

```text
WSL version: 2.7.12.0
Kernel version: 6.18.33.2-2
WSLg version: 1.0.73.2
Direct3D version: 1.611.1-81528511
Windows version: 10.0.26200.9168
```

**Ubuntu** — confirm the distro launched and identify itself:

```bash
lsb_release -a
uname -r
```

Expected: `Ubuntu 24.04 LTS` (codename `noble`).

> Do **not** run `apt update` or `apt upgrade` yet. On a corporate network those will
> partially fail in ways that are hard to interpret. Configure the proxy first — the
> system update is the last part of step 3.

Type `exit` to return to PowerShell.

---

## 3. Proxy configuration

**Do this before anything else that touches the network.** On a corporate network,
skipping it produces misleading failures much later.

### Why this trips people up

On the Intel network, **port 80 works directly but port 443 is blocked.** Ubuntu's own
package repositories are plain HTTP, so `sudo apt update` appears to succeed:

```text
Hit:1 http://archive.ubuntu.com/ubuntu noble InRelease        <-- port 80, works
Err:6 https://download.docker.com/linux/ubuntu noble InRelease <-- port 443, blocked
  Could not connect to download.docker.com:443, connection timed out
```

**A successful `apt update` does not prove your network is configured.**

If you are not behind a proxy, skip to [step 4](#4-base-packages).

### 3a. Windows side — `.wslconfig`

By default WSL2 uses NAT, and corporate endpoint-security agents frequently drop that
traffic. Mirrored networking makes WSL share the Windows network stack directly.

> **Mirrored networking requires WSL 2.0.0+ and Windows build 22621+.**
> Check with `wsl --version` and `[System.Environment]::OSVersion.Version` if unsure.
> On older builds, omit `networkingMode`, `dnsTunneling` and `firewall`, and set the
> proxy manually in step 3b.

Create or edit `C:\Users\<YourName>\.wslconfig`:

```ini
[wsl2]
networkingMode=mirrored
dnsTunneling=true
autoProxy=true
firewall=true
```

**PowerShell** — apply:

```powershell
wsl --shutdown
```

**Ubuntu** — verify. The address should now match your Windows IPv4, not `172.x.x.x`:

```bash
ip addr show eth0 | grep 'inet '
```

### 3b. Ubuntu shell — `~/.bashrc`

`autoProxy=true` injects `HTTP_PROXY` but **not** `HTTPS_PROXY`. Tools like `curl` read
`HTTPS_PROXY` for TLS connections, so without it they connect directly to port 443 and
hang. Mirror the value:

```bash
cat >> ~/.bashrc <<'EOF'

# WSL autoProxy sets HTTP_PROXY but not HTTPS_PROXY - mirror it
if [ -n "$HTTP_PROXY" ]; then
    export HTTPS_PROXY="${HTTPS_PROXY:-$HTTP_PROXY}"
    export http_proxy="$HTTP_PROXY"
    export https_proxy="$HTTPS_PROXY"
    export NO_PROXY="localhost,127.0.0.1,::1,.intel.com,10.0.0.0/8,rabbitmq,minio-service,rtsp-streamer,ovms-vlm,model-downloader"
    export no_proxy="$NO_PROXY"
fi
EOF

source ~/.bashrc
```

Verify:

```bash
env | grep -i proxy
curl -sI --max-time 15 https://download.docker.com/linux/ubuntu/gpg | head -1
```

The `curl` must return `HTTP/1.1 200` or `HTTP/2 200`. A hang means HTTPS is still
going direct.

> Find your proxy URL from `echo $HTTP_PROXY`, or from the PAC file WSL exposes as
> `$WSL_PAC_URL`. On the Intel India network it is `http://proxy-iind.intel.com:912`.

### 3c. apt — its own config file

**`apt` does not read shell environment variables.** It needs its own file. This is
separate from step 3b and both are required:

```bash
sudo tee /etc/apt/apt.conf.d/95proxies > /dev/null <<'EOF'
Acquire::http::Proxy "http://proxy-iind.intel.com:912";
Acquire::https::Proxy "http://proxy-iind.intel.com:912";
EOF
```

### 3d. Force IPv4

WSL2 has no IPv6 route. Without this, every apt download wastes ~30 seconds failing
over eight IPv6 addresses before trying IPv4:

```bash
sudo tee /etc/apt/apt.conf.d/99force-ipv4 > /dev/null <<'EOF'
Acquire::ForceIPv4 "true";
EOF
```

Verify both files:

```bash
cat /etc/apt/apt.conf.d/95proxies /etc/apt/apt.conf.d/99force-ipv4
```

### 3e. Update the base system

Only now is it safe to run this — every download path is configured:

```bash
sudo apt update
sudo apt upgrade -y
```

`apt update` must complete with **no `Err:` lines**. Warnings about missing repositories
you have not added yet are fine; connection timeouts are not.

### The four proxy contexts

Proxy settings live in four unrelated places. Configuring one tells you nothing about
the others:

| Context | Consumer | Location | Step |
|---|---|---|---|
| Shell | `curl`, `git`, `pip`, `wget` | `~/.bashrc` | 3b |
| apt | `sudo apt` | `/etc/apt/apt.conf.d/95proxies` | 3c |
| Daemon | `docker pull` | `/etc/systemd/system/docker.service.d/proxy.conf` | 7 |
| Build | `docker build` RUN steps | `~/.docker/config.json` | 8 |

Steps 7 and 8 come later because those paths do not exist until Docker is installed.

> `sudo` strips proxy environment variables. Use `sudo -E` for any command that needs
> network access.

---

## 4. Base packages

```bash
sudo apt install -y \
  build-essential make git curl wget unzip \
  jq python3 python3-pip python3-venv \
  ca-certificates gnupg lsb-release
```

| Package | Used by |
|---|---|
| `make` | every workflow command (`make run-lp`, `make benchmark`) |
| `jq` | `model-downloader.sh` and `check-device-env` parse `configs/*.json` |
| `python3` + `venv` | `download-video.py`, config validators, benchmark scripts |
| `curl` / `wget` | model and video downloads |
| `git` | the repo and the `performance-tools` submodule |

Verify:

```bash
make --version && jq --version && python3 --version && git --version
```

---

## 5. Enable systemd

Docker Engine runs as a systemd service. WSL2 does not enable systemd by default.

```bash
sudo tee /etc/wsl.conf > /dev/null <<'EOF'
[boot]
systemd=true

[interop]
appendWindowsPath=true
EOF
```

**PowerShell** — a full shutdown is required; closing the terminal is not enough:

```powershell
wsl --shutdown
```

Reopen Ubuntu and verify:

```bash
ps -p 1 -o comm=
systemctl list-units --type=service | head
```

`ps -p 1 -o comm=` must print `systemd`. If you see
`System has not been booted with systemd`, the shutdown did not take effect.

---

## 6. Install Docker Engine

### Why Docker Engine and not Docker Desktop

Docker Desktop runs its daemon in a **separate hidden distro** (`docker-desktop`), not
in your Ubuntu. For the GPU work in step 11 you will bind-mount `/usr/lib/wsl/lib` and
pass `--device=/dev/dxg`; cross-distro path translation makes failures much harder to
diagnose. With Docker Engine installed inside Ubuntu-24.04, the daemon sees exactly the
same devices and filesystem you do.

> Do not install both. Two daemons will conflict.

### Add Docker's GPG key

```bash
sudo install -m 0755 -d /etc/apt/keyrings
sudo -E curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
```

**Verify before continuing.** A timed-out `curl` leaves an empty file, and the resulting
apt error is misleading:

```bash
head -1 /etc/apt/keyrings/docker.asc
```

Must print `-----BEGIN PGP PUBLIC KEY BLOCK-----`.

### Add the repository and install

```bash
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin
```

### Enable non-root access

```bash
sudo usermod -aG docker $USER
sudo systemctl enable --now docker
```

Group membership is only read at login. **PowerShell:**

```powershell
wsl --shutdown
```

Reopen Ubuntu and verify:

```bash
id -nG | tr ' ' '\n' | grep docker
docker run hello-world
docker compose version
docker buildx version
```

`docker compose version` must report **v2.x** — the Makefile uses `docker compose`
(space, not hyphen) throughout.

> Do not work around permission errors with `sudo docker`. Running as root creates
> root-owned files in `models/` and `results/`, which breaks later steps.

---

## 7. Docker daemon proxy

Required for `docker pull`. The daemon is a system service and does not inherit your
shell environment:

```bash
sudo mkdir -p /etc/systemd/system/docker.service.d
sudo tee /etc/systemd/system/docker.service.d/proxy.conf > /dev/null <<'EOF'
[Service]
Environment="HTTP_PROXY=http://proxy-iind.intel.com:912"
Environment="HTTPS_PROXY=http://proxy-iind.intel.com:912"
Environment="NO_PROXY=localhost,127.0.0.1,.intel.com,rabbitmq,minio-service,rtsp-streamer,ovms-vlm,model-downloader"
EOF

sudo systemctl daemon-reload
sudo systemctl restart docker
```

Verify:

```bash
docker info | grep -i proxy
```

You should see `HTTP Proxy`, `HTTPS Proxy` and `No Proxy` lines. If they are absent,
the drop-in did not load.

---

## 8. Docker build-time proxy

Each `RUN` instruction in a Dockerfile executes in a throwaway container with a clean
environment. It does not inherit your shell's proxy settings.

The Makefile and compose file already pass `HTTP_PROXY`/`HTTPS_PROXY` as build args for
the project's own images, but coverage has gaps:

- `make build-benchmark` delegates to the `performance-tools` submodule's Makefile,
  which is outside this repo's proxy plumbing
- Only `rtsp-streamer` passes the lowercase `http_proxy`/`https_proxy` variants;
  `curl` reads lowercase `http_proxy` **only**, so `RUN curl http://...` in the other
  images would bypass the proxy
- `NO_PROXY` is not passed as a build arg anywhere

Setting the CLI-level config covers all of these uniformly:

```bash
mkdir -p ~/.docker
cat > ~/.docker/config.json <<'EOF'
{
  "proxies": {
    "default": {
      "httpProxy": "http://proxy-iind.intel.com:912",
      "httpsProxy": "http://proxy-iind.intel.com:912",
      "noProxy": "localhost,127.0.0.1,.intel.com,rabbitmq,minio-service,rtsp-streamer,ovms-vlm,model-downloader"
    }
  }
}
EOF
```

---

## 9. Memory and CPU tuning

The VLM workload loads a 7B parameter model. Defaults are not sufficient.

Edit `C:\Users\<YourName>\.wslconfig` on the **Windows** side, merging with the
networking settings from step 3a:

```ini
[wsl2]
memory=48GB
processors=12
swap=16GB
networkingMode=mirrored
dnsTunneling=true
autoProxy=true
firewall=true
```

> `localhostForwarding` is unnecessary when `networkingMode=mirrored` is set.

**PowerShell:**

```powershell
wsl --shutdown
```

**Ubuntu** — verify:

```bash
free -h
nproc
df -h /
```

The repository plus models needs roughly **300 GB**. The WSL virtual disk lives on your
Windows `C:` drive, so `df -h /` reflects free space there.

---

## 10. Clone the repository

```bash
cd ~
git clone https://github.com/intel-retail/loss-prevention.git
cd loss-prevention
git submodule update --init --recursive
```

Two things to get right:

1. **Never clone into `/mnt/c/...`.** Windows drives are reached through a slow
   translation layer. Always use `~`, which is the native Linux filesystem.
2. **The submodule is mandatory.** `performance-tools/` holds every benchmark script.

Verify the submodule checked out:

```bash
ls performance-tools/benchmark-scripts | head
```

You should see `benchmark.py` and `format_avc_mp4.sh`. An empty directory means the
submodule did not initialize.

Record your baseline:

```bash
git rev-parse --short HEAD
git submodule status
```

### Optional: repository-scoped environment

The Makefile reads an optional `.env` file. Proxy variables do **not** need to go here —
`make` already imports them from your shell environment. Use `.env` only for values that
should not be global, such as secrets:

```bash
# .env  (do not commit)
HUGGINGFACE_TOKEN=hf_xxxxxxxx
```

---

## 11. GPU and NPU verification

This is the go/no-go check for the whole port.

### Do NOT install Intel GPU drivers via apt

On native Linux you would follow the `dgpu-docs.intel.com` guide and install
`intel-opencl-icd`, `intel-level-zero-gpu` and similar packages. **Under WSL2 that is
wrong and will break GPU access.**

In WSL, the Intel *Windows* driver projects its Linux-side libraries into the distro at
`/usr/lib/wsl/lib`. Installing the apt packages places conflicting versions in
`/usr/lib/x86_64-linux-gnu` that shadow them.

The same applies to the NPU — there is no `intel_vpu` kernel module to install.

If the GPU is missing, the fix is always on the **Windows** side: install the latest
Intel graphics driver, then `wsl --shutdown`.

### 11a. Host device check

```bash
ls -l /dev/dxg
ls -l /usr/lib/wsl/lib/
ls /dev/dri 2>&1
ls /dev/accel 2>&1
```

Expected results:

| Path | Expected | Meaning |
|---|---|---|
| `/dev/dxg` | **exists** | the WSL GPU device — replaces `/dev/dri` |
| `/usr/lib/wsl/lib/` | populated | `libd3d12.so`, `libd3d12core.so`, `libdxcore.so` plus Intel compute libraries |
| `/dev/dri` | **absent** | expected; this is why the compose device mappings need changing |
| `/dev/accel` | likely absent | the NPU finding |

If `/dev/dxg` is missing, stop here and update the Windows graphics driver.

### 11b. OpenVINO device enumeration

```bash
docker run --rm \
  --device=/dev/dxg \
  -v /usr/lib/wsl/lib:/usr/lib/wsl/lib \
  -e LD_LIBRARY_PATH=/usr/lib/wsl/lib \
  openvino/ubuntu24_dev:latest \
  python3 -c "import openvino as ov; print(ov.Core().available_devices)"
```

**Want:** `['CPU', 'GPU']`

If only `['CPU']` appears, inspect what the runtime can actually see:

```bash
docker run --rm \
  --device=/dev/dxg \
  -v /usr/lib/wsl/lib:/usr/lib/wsl/lib \
  -e LD_LIBRARY_PATH=/usr/lib/wsl/lib \
  openvino/ubuntu24_dev:latest \
  bash -c "ls /usr/lib/wsl/lib/ && clinfo -l 2>&1 | head"
```

### 11c. NPU

```bash
ls /dev/accel 2>&1
lsmod | grep -i vpu
```

If `NPU` does not appear in the OpenVINO device list, that is the expected result on
current WSL2 builds, not a mistake on your part. Intel NPU passthrough uses a different
mechanism from GPU passthrough and may not be available for your driver and kernel
combination. A documented "not supported" is a valid outcome.

### 11d. Record the baseline

```bash
{
  echo "=== /dev/dxg ==="   ; ls -l /dev/dxg   2>&1
  echo "=== /dev/dri ==="   ; ls -l /dev/dri   2>&1
  echo "=== /dev/accel ===" ; ls -l /dev/accel 2>&1
  echo "=== /usr/lib/wsl/lib ==="; ls /usr/lib/wsl/lib/
  echo "=== kernel ==="     ; uname -r
} | tee ~/wsl-accel-baseline.txt
```

---

## 12. Smoke test

Run in order, stopping at the first failure:

```bash
cd ~/loss-prevention

# 1. Docker works
docker run hello-world

# 2. The Makefile parses and resolves variables
make -n run-lp | head -20

# 3. Config validators work (proves python3 and jq are fine)
make validate-all-configs

# 4. What devices does the repo think you have?
make check-device-env

# 5. Sample videos - small download, fast feedback
make download-sample-videos
```
---