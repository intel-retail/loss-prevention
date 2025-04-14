# Loss Prevention

![Integration](https://github.com/intel-retail/loss-prevention/actions/workflows/integration.yaml/badge.svg?branch=main)
![CodeQL](https://github.com/intel-retail/loss-prevention/actions/workflows/codeql.yaml/badge.svg?branch=main)
![GolangTest](https://github.com/intel-retail/loss-prevention/actions/workflows/gotest.yaml/badge.svg?branch=main)
![DockerImageBuild](https://github.com/intel-retail/loss-prevention/actions/workflows/build.yaml/badge.svg?branch=main) 
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/intel-retail/loss-prevention/badge)](https://api.securityscorecards.dev/projects/github.com/intel-retail/loss-prevention)
[![GitHub Latest Stable Tag](https://img.shields.io/github/v/tag/intel-retail/loss-prevention?sort=semver&label=latest-stable)](https://github.com/intel-retail/loss-prevention/releases)
[![Discord](https://discord.com/api/guilds/1150892043120414780/widget.png?style=shield)](https://discord.gg/2SpNRF4SCn)

> **Warning**  
> The **main** branch of this repository contains work-in-progress development code for the upcoming release, and is **not guaranteed to be stable or working**.
>
> **The source for the latest release can be found at [Releases](https://github.com/intel-retail/loss-prevention/releases).**

# Table of Contents 📑

- [📋 Prerequisites](#-prerequisites)
- [🚀 QuickStart](#-quickstart)
  - [Run pipeline with Grafana](#run-pipeline-with-grafana)
  - [Run pipeline with classification model on iGPU]
- [📊 Benchmarks](#-benchmarks)
- [📖 Advanced Documentation](#-advanced-documentation)
- [🌀 Join the community](#-join-the-community)
- [References](#references)
- [Disclaimer](#disclaimer)
- [Datasets & Models Disclaimer](#datasets--models-disclaimer)
- [License](#license)

## 📋 Prerequisites

- [Docker](https://docs.docker.com/engine/install/ubuntu/) 
- [Manage Docker as a non-root user](https://docs.docker.com/engine/install/linux-postinstall/)
- [Docker Compose v2](https://docs.docker.com/compose/) (Optional)
- Make (sudo apt install make)
- Intel hardware (CPU, GPU, dGPU)

## 🚀 QuickStart

(If this is the first time, it will take some time to download videos, models, docker images and build containers)

```
make run-demo
```

stop containers:

```
make down
```

## Run Pipeline with Grafana

```
RTSP=1 make run-demo
```

Open grafana dashboard:

🔗 [Grafana Dashboard](http://127.0.0.1:3000/d/ce428u65d0irkf/loss-prevention?from=now-6h&to=now&timezone=browser&refresh=2s)

![Grafana](<grafana.jpg>)

## 📊 Benchmarks

Go here for [the documentation of loss prevention pipeline benchmarking](./benchmark.md)


## 📖 Advanced Documentation

[Loss Prevention Documentation Guide](https://intel-retail.github.io/documentation/use-cases/loss-prevention/loss-prevention.html)

## 🌀 Join the community 
[![Discord Banner 1](https://discordapp.com/api/guilds/1150892043120414780/widget.png?style=banner2)](https://discord.gg/2SpNRF4SCn)

## References

- [Developer focused website to enable developers to engage and build our partner community](https://www.intel.com/content/www/us/en/developer/articles/reference-implementation/loss-prevention.html)

- [LinkedIn blog illustrating the Loss Prevention use case more in detail](https://www.linkedin.com/pulse/retail-innovation-unlocked-open-source-vision-enabled-mohideen/)

## Disclaimer

GStreamer is an open source framework licensed under LGPL. See https://gstreamer.freedesktop.org/documentation/frequently-asked-questions/licensing.html?gi-language=c.  You are solely responsible for determining if your use of Gstreamer requires any additional licenses.  Intel is not responsible for obtaining any such licenses, nor liable for any licensing fees due, in connection with your use of Gstreamer.

Certain third-party software or hardware identified in this document only may be used upon securing a license directly from the third-party software or hardware owner. The identification of non-Intel software, tools, or services in this document does not constitute a sponsorship, endorsement, or warranty by Intel.

## Datasets & Models Disclaimer

To the extent that any data, datasets or models are referenced by Intel or accessed using tools or code on this site such data, datasets and models are provided by the third party indicated as the source of such content. Intel does not create the data, datasets, or models, provide a license to any third-party data, datasets, or models referenced, and does not warrant their accuracy or quality.  By accessing such data, dataset(s) or model(s) you agree to the terms associated with that content and that your use complies with the applicable license.

Intel expressly disclaims the accuracy, adequacy, or completeness of any data, datasets or models, and is not liable for any errors, omissions, or defects in such content, or for any reliance thereon. Intel also expressly disclaims any warranty of non-infringement with respect to such data, dataset(s), or model(s). Intel is not liable for any liability or damages relating to your use of such data, datasets or models.

## License
This project is Licensed under an Apache [License](./LICENSE.md).