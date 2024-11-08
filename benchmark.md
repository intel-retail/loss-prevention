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
    For more details on how this works, you can check the documentation of performance-tools in [Benchmark a CV Pipeline](https://github.com/intel-retail/documentation/blob/main/docs_src/performance-tools/benchmark.md#benchmark-a-cv-pipeline) section.

2. Benchmarking the stream density of the loss-prevention pipelines:

```bash
make benchmark-stream-density
```

!!! Note
    For more details on how this works, you can check the documentation of performance-tools in [Benchmark Stream Density for CV Pipelines](https://github.com/intel-retail/documentation/blob/main/docs_src/performance-tools/benchmark.md#benchmark-stream-density-for-cv-pipelines) section.

### Benchmark for multiple pipelines in parallel

There is an example docker-compose file under src/ directory, named `docker-compose-2-clients.yml` that can be used to show case both of benchmarks of parallel running pipelines and stream density benchmarks of running pipelines.  This docker-compose file contains two different running pipelines: one is running yolov5s pipeline and the other one is yolov8 region of interests pipeline.  Follow the follow command examples to do the benchmarks:

```bash
make update-submodules
```

and then re-build the whole benchmark tools:

```bash
make build-benchmark
```

then clean up the previous results to have a fresh start:

```bash
make clean-benchmark-results
```

and then you can benchmark multiple different running pipelines in that compose file via:

```bash
make DOCKER_COMPOSE=docker-compose-2-clients.yml BENCHMARK_DURATION=90 benchmark
```

!!! Note
    BENCHMARK_DURATION is proveded to have longer time for pipelines as more pipelines running in parallel in the docker-compose tend to slow down the system and need more time for all pipelines to be stabilized. Adjust this input accordingly for your hardware system.

and then you can also do the stream density of both running pipelines in this docker-compose file via the following command:

```bash
make DOCKER_COMPOSE=docker-compose-2-clients.yml BENCHMARK_DURATION=90 TARGET_FPS="10.95 2.95" CONTAINER_NAMES="gst1 gst2" benchmark-stream-density
```

!!! Note
    The stream density benchmarks can take long time depending on your hardware system.  Please allow it to run until to the end to see the benchmark result.


## Tuning Benchmark Parameters

You can tune some benchmark parameters when you benchmark loss-prevention pipelines:

| Parameter Name         | Default Value   | Description                                                          |
| -----------------------|-----------------|----------------------------------------------------------------------|
| PIPELINE_COUNT         | 1               | number of loss-prevention pipelines to launch for benchmarking       |
| BENCHMARK_DURATION     | 45              | the time period of benchmarking will be run in second                |
| TARGET_FPS             | 14.95           | used for stream density maintaining that target frames per second (fps) while having maximum number of pipelines running and this can be multiple values with whitespace delimited for multiple running pipelines |
| CONTAINER_NAMES        | gst0            | used for stream density to have target container name list for multiple running pipelines and paired with TARGET_FPS to have 1-to-1 mapping with the pipeline |
| DENSITY_INCREMENT      | 1               | used for stream density to set the pipeline increment number for each iteration |
| RESULTS_DIR            | ./results       | the directory of the outputs for running pipeline logs and fps info  |
| PIPELINE_SCRIPT        | yolov5s.sh      | the script to run the pipeline, for yolov8, you can use yolov8s_roi.sh for running region of interest pipeline |
| RENDER_MODE            | 0               | when it is set to 1, another popup winodw will display the input source video and some of inferencing results like bounding boxes and/or region of interests |

As an example, the following command with parameter `PIPELINE_COUNT` will do the benchmark for 2 loss-prevention pipelines:

```bash
 PIPELINE_COUNT=2 make benchmark
```

## Clean up

To clean up all the benchmark results, run the command:

```bash
make clean-benchmark-results
```

This comes in handy when you want to have a new set of benchmarks for different benchmark use cases like different pipelines or running duration.
