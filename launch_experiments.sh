#!/bin/bash

# Function to launch simulations in parallel. Use as 
# parallel_sim_launch <executable> <file containing names of traces>
# Launches sim for 20mil warmup + 50mil instructions
parallel_sim_launch() {
  BINARY=$1
  TRACENAMES_FILE=$2
  BATCH_SIZE=8
  counter=0
  while IFS= read -r line; do
    ./bin/$BINARY --warmup_instructions 10000000 --simulation_instructions 100000000 --trace CRC2_traces/$line > results_2mb_noprefetch_shippp_maxrrpv_2/$line.txt &
    let counter++
    if [ $counter -ge $BATCH_SIZE ]
    then
      let counter=0
      echo "launched 8 experiments, sleeping..."
      sleep 10m
    fi
  done < $TRACENAMES_FILE
}  

# Experiment definations
# Experiments: launch set of binaries with different configs on the same traces
experiment_worst_l1Imiss_djolt() {
  for binary in "$@"
  do
    parallel_sim_launch $binary trace_names_worst_L1Imiss_djolt.txt
    sleep 5m
  done
}

experiment_worst_l1Imiss_fnlmma() {
  for binary in "$@"
  do
    parallel_sim_launch $binary trace_names_worst_L1Imiss_fnlmma.txt
    sleep 4m
  done
}

experiment_server() {
  for binary in "$@"
  do
    parallel_sim_launch $binary trace_names_server.txt
    sleep 5m
  done
}

experiment_client() {
  for binary in "$@"
  do
    parallel_sim_launch $binary trace_names_client.txt
    sleep 5m
  done
}

experiment_spec() {
  for binary in "$@"
  do
    parallel_sim_launch $binary trace_names_spec.txt
    sleep 5m
  done
}

experiment_alltraces() {
  for binary in "$@"
  do
    parallel_sim_launch $binary alltraces.txt
    sleep 5m
  done
}


#experiment_server hashed_perceptron-FNL-MMA280520-next_line-spp_dev-no-lru-1core
#experiment_client hashed_perceptron-FNL-MMA280520-next_line-spp_dev-no-lru-1core
#experiment_spec hashed_perceptron-FNL-MMA280520-next_line-spp_dev-no-lru-1core

#experiment_server hashed_perceptron-D_JOLT-next_line-spp_dev-no-lru-1core
#experiment_client hashed_perceptron-D_JOLT-next_line-spp_dev-no-lru-1core
#experiment_spec hashed_perceptron-D_JOLT-next_line-spp_dev-no-lru-1core

### Design space exploration

#experiment_worst_l1Imiss_djolt djolt_siggen_9_2 djolt_siggen_6_5 djolt_siggen_8_3
#experiment_worst_l1Imiss_djolt djolt_siggen_8_3_hdist_13_6 djolt_siggen_8_3_hdist_14_5 djolt_siggen_8_3_hdist_16_3 djolt_siggen_8_3_hdist_17_2
#experiment_worst_l1Imiss_djolt djolt_siggen_8_3_hdist_16_3_ways_4_8 djolt_siggen_8_3_hdist_16_3_ways_8_4 djolt_siggen_8_3_hdist_16_3_ways_8_8
#experiment_worst_l1Imiss_djolt djolt_siggen_8_3_hdist_16_3_sets_2048_2048 djolt_siggen_8_3_hdist_16_3_sets_4096_1024
#experiment_worst_l1Imiss_djolt djolt_siggen_8_3_hdist_16_3_sets_1024_1024 djolt_siggen_8_3_hdist_16_3_sets_1024_512 djolt_siggen_8_3_hdist_16_3_sets_2048_512
#experiment_worst_l1Imiss_fnlmma fnlmma_reset_4k fnlmma_reset_5k fnlmma_reset_12k fnlmma_reset_16k
#experiment_worst_l1Imiss_fnlmma fnlmma_dist_7 fnlmma_dist_8 fnlmma_dist_9 fnlmma_dist_11 fnlmma_dist_12
#experiment_worst_l1Imiss_fnlmma fnlmma_dist_13 fnlmma_dist_14 fnlmma_dist_15 fnlmma_dist_16
#experiment_worst_l1Imiss_fnlmma fnlmma_half_tables fnlmma_fourth_tables

#experiment_alltraces champsim-llc-2mb-noprefetch-shippp
#experiment_alltraces champsim-llc-2mb-noprefetch-hawkeye
experiment_alltraces champsim-llc-2mb-noprefetch-shippp-maxrrpv-2
