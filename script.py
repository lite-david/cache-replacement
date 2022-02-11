from archlib import Analyzer, LaunchExperiment
import os

def launch_run(binary_name):
    r = LaunchExperiment(binary=binary_name, 
                        bindir='bin',
                        warmup_inst= 10000000,
                        simulation_inst= 100000000,
                        tracelist='alltraces.txt',
                        tracedir='CRC2_traces',
                        batchsize=24)
    r.run()


def launch_runs(grep_str):
    bins = os.listdir('bin')
    for b in bins:
        if b.find(grep_str) != -1:
            r = LaunchExperiment(binary=b, 
                                bindir='bin',
                                warmup_inst= 10000000,
                                simulation_inst= 100000000,
                                tracelist='alltraces.txt',
                                tracedir='CRC2_traces',
                                batchsize=24)
            r.run()


def get_result(result_dir):
    analyzer = Analyzer(result_dir)
    analyzer.gencsv(f'{result_dir}.csv')

def get_results():
    result_dirs = os.listdir('.')
    for result_dir in result_dirs:
        if result_dir.startswith('results') and not os.path.isfile(result_dir):
            get_result(result_dir)

#launch_runs("shippp-maxrrpv")
#launch_runs("shippp-maxshctr")
#launch_runs("leaders")
#launch_runs("sampler")
#launch_runs("hawkeye-maxrrpv")
#launch_runs("optgenvector")
get_results()
