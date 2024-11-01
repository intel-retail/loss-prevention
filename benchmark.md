# Benchmark Loss Prevention Pipelines

## Prerequisites for benchmark tools

Before running any benchmark on the loss prevention pipelines, please check the [prerequisites documentation of performance-tool benchmark](https://github.com/intel-retail/documentation/blob/main/docs_src/performance-tools/benchmark.md#prerequisites) and make you have those set up and installed.

## Run Benchmark Use Cases

When in the loss-prevention project base directory, make sure you have the latest code from performance-tool repo via running the following command:

```bash
make update-submodules
```

and then build the whole benchmark tools:

```bash
make build-benchmark
```

Once benchmark tools are built, there are two categories to do the benchmark:

1. Benchmarking the loss-prevention running pipelines:

```bash
make benchmark
```

!!! Note
    For more detials on how this works, you can check the the documentation of performance-tools in [Benchmark a CV Pipeline](https://github.com/intel-retail/documentation/blob/main/docs_src/performance-tools/benchmark.md#benchmark-a-cv-pipeline) section.

1. Benchmarking the stream density of the loss-prevention pipelines:

```bash
make benchmark-stream-density
```

!!! Note
    For more detials on how this works, you can check the the documentation of performance-tools in [Benchmark Stream Density for CV Pipelines](https://github.com/intel-retail/documentation/blob/main/docs_src/performance-tools/benchmark.md#benchmark-stream-density-for-cv-pipelines) section.

## Tuning Benchmark Parameters

You can tune some benchmark paramters when you benchmark loss-prevention pipelines:

| Parameter Name         | Default Value   | Description                                                          |
| -----------------------|-----------------|----------------------------------------------------------------------|
| PIPELINE_COUNT         | 1               | number of loss-prevention pipelines to launch for benchmarking       |
| BENCHMARK_DURATION     | 45              | the time period of benchmarking will be run in second                |
| TARGET_FPS             | 14.95           | used for stream density maintaining that target frames per second (fps) while having maximum number of pipelines running |
| RESULTS_DIR            | ./results       | the directory of the outputs for running pipeline logs and fps info  |
| PIPELINE_SCRIPT        | yolov5s.sh      | the script to run the pipeline, for yolov8, you can use yolov8s_roi.sh for running region of interest pipeline |
| RENDER_MODE            | 0               | to display the input source video and some of inferencing results like bounding boxes and/or region of interests |


As an example, the following command with parameter `PIPELINE_COUNT` will do the benchmark for 2 loss-prevention pipelines:

```bash
 PIPELINE_COUNT=2 make benchmark
```

## Clean up

To clean up all the benchmark results, run the command:

```bash
make clean-benchmark-results
```

This comes handy when you want to have a new set of benchmark for different benchmark use cases like different pipelines or running duration.
