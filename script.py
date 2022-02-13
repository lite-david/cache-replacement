from archlib import Analyzer, LaunchExperiment, HarryPlotter
import os
import pandas as pd

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
            launch_run(b)


def get_result(result_dir):
    analyzer = Analyzer(result_dir)
    analyzer.gencsv(f'{result_dir}.csv')

def get_results():
    result_dirs = os.listdir('.')
    for result_dir in result_dirs:
        if result_dir.startswith('results') and not os.path.isfile(result_dir):
            get_result(result_dir)

def plot(feature, dirname):
    csvs = os.listdir(dirname)
    ipc_data = []
    l2_lat_data = []
    mpki_data = []
    csv_list = []
    for csv in csvs:
        if csv.find(feature) != -1:
            csv_list.append(f'{dirname}/{csv}')
    hp = HarryPlotter()
    hp.agg(csv_list, feature)
    hp.plotmetrics(['ipc', 'l2_latency', 'mpki'])

def plotbox():
    hp = HarryPlotter()
    hp.load(['analysis/results_champsim-llc-2mb-noprefetch-lru.csv',
             'analysis/results_champsim-llc-2mb-noprefetch-ship.csv',
             'analysis/results_champsim-llc-2mb-noprefetch-hawkeye.csv',
             'analysis/results_champsim-llc-2mb-noprefetch-shippp.csv',],
              columns=['Cumulative IPC'], names=['lru', 'ship', 'hawkeye', 'ship++'])
    hp.plotboxplot(names=['lru', 'ship', 'hawkeye', 'ship++'], column='Cumulative IPC')

def genplots():
    plot("hawkeye-maxrrpv", 'analysis')
    plot("hawkeye-sampler", 'analysis')
    plot("hawkeye-optgenvector", 'analysis')
    plot("shippp-maxrrpv", 'analysis')
    plot("shippp-maxshctr", 'analysis')
    plot("shippp-leaders", 'analysis')


#launch_runs("shippp-maxrrpv")
#launch_runs("shippp-maxshctr")
#launch_runs("leaders")
#launch_runs("sampler")
#launch_runs("hawkeye-maxrrpv")
#launch_runs("optgenvector")
#get_results()
#get_result("results_champsim-llc-2mb-noprefetch-shippp-maxrrpv-4")
#get_result("results_champsim-llc-2mb-noprefetch-ship")
#genplots()
plotbox()

