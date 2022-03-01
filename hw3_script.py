from archlib import Analyzer, LaunchExperiment, HarryPlotter, Experiment
import os
import pandas as pd
from scipy import stats

def launch_run(binary_name, tracelist='alltraces.txt'):
    r = LaunchExperiment(binary=binary_name, 
                        bindir='bin',
                        warmup_inst= 10000000,
                        simulation_inst= 100000000,
                        tracelist=tracelist,
                        tracedir='CRC2_traces',
                        batchsize=8)
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
             'analysis/results_champsim-llc-2mb-noprefetch-shippp.csv',
             'analysis/results_champsim-llc-2mb-noprefetch-hawkeye.csv'],
              columns=['Cumulative IPC', 'LLC TOTAL MISS'], names=['lru', 'ship', 'ship++', 'hawkeye'])
    for name in hp.data.keys():
        gmean = stats.gmean(hp.data[name]['Cumulative IPC'])
        hp.data[name]['MPKI'] = hp.data[name]['LLC TOTAL MISS']/100000
        mean_mpki = hp.data[name]['MPKI'].mean()
        print(f'{name} geomean IPC: {gmean}')
        print(f'{name} avg MPKI: {mean_mpki}')
    hp.plotboxplot(names=['lru', 'ship', 'ship++', 'hawkeye'], column='Cumulative IPC')
    hp.plotboxplot(names=['lru', 'ship', 'ship++', 'hawkeye'], column='MPKI')

def genplots():
    #plot("shippp-maxrrpv", 'analysis')
    #plot("shippp-maxshctr", 'analysis')
    plot("shippp-shctsize", 'analysis')
    plot("hawkeye-maxrrpv", 'analysis')
    plot("hawkeye-sampler", 'analysis')
    plot("hawkeye-optgenvector", 'analysis')


def gen_binaries():
    e = Experiment('champsim_config.json')
    for maxpsel in [64, 128, 256, 512]:
        e.config['executable_name'] = 'bin/rocketship-hysterisis-maxpsel-' + str(maxpsel)
        e.config['LLC']['replacement'] = 'rocketship-hysterisis'
        e.config['LLC']['rocketship-hysterisis'] = {
            'MAXPSEL': maxpsel,
        }
        e.compile_bin()
    e.config['executable_name'] = 'bin/rocketship-staticsample'
    e.config['LLC']['replacement'] = 'rocketship-staticsample'
    e.compile_bin()
    
#launch_run('rocketship', tracelist='memfootprint_traces.txt')
#get_result('results_rocketship')
gen_binaries()
launch_runs('rocketship-hysterisis-maxpsel')
get_results('rocketship-hysterisis-maxpsel')

