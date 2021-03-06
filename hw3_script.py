from archlib import Analyzer, LaunchExperiment, HarryPlotter, Experiment
import os
import pandas as pd
from scipy import stats
import multiprocessing as mp
import argparse

def launch_run(binary_name, tracelist='alltraces.txt'):
    r = LaunchExperiment(binary=binary_name, 
                        bindir='bin',
                        warmup_inst= 10000000,
                        simulation_inst= 100000000,
                        tracelist=tracelist,
                        tracedir='CRC2_traces',
                        batchsize=mp.cpu_count())
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
    hp.plotmetrics(['ipc', 'mpki'])

def plotbox():
    hp = HarryPlotter()
    hp.load(['hw3_analysis/hysterisis-policyswitches.txt',
             'hw3_analysis/nohysterisis-policyswitches.txt'],
              columns=['switches'], names=['hysteresis', 'nohysteresis'])
    hp.plotboxplot(names=['nohysteresis', 'hysteresis'], column='switches', showfliers=True)

def genplots():
    #plot("shippp-maxrrpv", 'analysis')
    #plot("shippp-maxshctr", 'analysis')
    plot("rocketship-hysterisis-maxpsel", 'hw3_analysis')


def gen_binaries():
    e = Experiment('champsim_config.json')

    # binaries to find best psel value
    for maxpsel in [64, 128, 256, 512, 1024, 2048]:
        e.config['executable_name'] = 'bin/rocketship-hysterisis-maxpsel-' + str(maxpsel)
        e.config['LLC']['replacement'] = 'rocketship-hysterisis'
        e.config['LLC']['rocketship-hysterisis'] = {
            'MAXPSEL': maxpsel,
            'HYSTERISIS':'true',
            'ISOLATE_RRPV':'false',
            'FILTER_WB':'true',
            'SHIPPP_SHCT_SIZE':'(1 << 14)',
            'OPTGEN_VECTOR_SIZE':128,
            'SAMPLED_CACHE_SIZE':2800,
            'NUM_LEADER_SETS':64
        }
        e.compile_bin()
    # config 32KB budget, no wb filtering    
    e.config['executable_name'] = 'bin/rocketship-hysterisis-small-nowb'
    e.config['LLC']['replacement'] = 'rocketship-hysterisis'
    e.config['LLC']['rocketship-hysterisis'] = {
        'MAXPSEL': 512,
        'ISOLATE_RRPV':'false',
        'HYSTERISIS':'true',
        'ISOLATE_RRPV_COND':'((set%8)==0)',
        'FILTER_WB':'false',
        'SHIPPP_SHCT_SIZE':'(1 << 13)',
        'SHCT_SIZE_BITS': 11,
        'OPTGEN_VECTOR_SIZE':64,
        'SAMPLED_CACHE_SIZE':3984,
        'NUM_LEADER_SETS':32
    }
    e.compile_bin()


    # config 32KB budget, highest IPC within the budget    
    e.config['executable_name'] = 'bin/rocketship-hysterisis-small'
    e.config['LLC']['replacement'] = 'rocketship-hysterisis'
    e.config['LLC']['rocketship-hysterisis'] = {
        'MAXPSEL': 512,
        'ISOLATE_RRPV':'false',
        'HYSTERISIS':'true',
        'ISOLATE_RRPV_COND':'((set%8)==0)',
        'FILTER_WB':'true',
        'SHIPPP_SHCT_SIZE':'(1 << 13)',
        'SHCT_SIZE_BITS': 11,
        'OPTGEN_VECTOR_SIZE':64,
        'SAMPLED_CACHE_SIZE':3984,
        'NUM_LEADER_SETS':32
    }
    e.compile_bin()
    
    # config within 32KB budget, with selected sets rrpv counters isolated
    e.config['executable_name'] = 'bin/rocketship-hysterisis-small-isolaterrpv'
    e.config['LLC']['replacement'] = 'rocketship-hysterisis'
    e.config['LLC']['rocketship-hysterisis'] = {
        'MAXPSEL': 512,
        'ISOLATE_RRPV':'true',
        'HYSTERISIS':'true',
        'ISOLATE_RRPV_COND':'((set%8)==0)',
        'FILTER_WB':'true',
        'SHIPPP_SHCT_SIZE':'(1 << 13)',
        'SHCT_SIZE_BITS': 11,
        'OPTGEN_VECTOR_SIZE':64,
        'SAMPLED_CACHE_SIZE':3296,
        'NUM_LEADER_SETS':32
    }
    e.compile_bin()
    
    # config with higher budget, rrpv isolation, higher sampler size
    e.config['executable_name'] = 'bin/rocketship-hysterisis-large'
    e.config['LLC']['replacement'] = 'rocketship-hysterisis'
    e.config['LLC']['rocketship-hysterisis'] = {
        'MAXPSEL': 512,
        'ISOLATE_RRPV':'true',
        'HYSTERISIS':'true',
        'ISOLATE_RRPV_COND':'true',
        'FILTER_WB':'true',
        'SHIPPP_SHCT_SIZE':'(1 << 15)',
        'SHCT_SIZE_BITS': 13,
        'OPTGEN_VECTOR_SIZE':128,
        'SAMPLED_CACHE_SIZE':5600,
        'NUM_LEADER_SETS':128
    }
    e.compile_bin()

    # config with no hysterisis
    e.config['executable_name'] = 'bin/rocketship-hysterisis-small-nohysterisis'
    e.config['LLC']['replacement'] = 'rocketship-hysterisis'
    e.config['LLC']['rocketship-hysterisis'] = {
        'MAXPSEL': 512,
        'ISOLATE_RRPV':'false',
        'HYSTERISIS':'false',
        'ISOLATE_RRPV_COND':'((set%8)==0)',
        'FILTER_WB':'true',
        'SHIPPP_SHCT_SIZE':'(1 << 13)',
        'SHCT_SIZE_BITS': 11,
        'OPTGEN_VECTOR_SIZE':64,
        'SAMPLED_CACHE_SIZE':3984,
        'NUM_LEADER_SETS':32
    }
    e.compile_bin()
    
#launch_run('rocketship', tracelist='memfootprint_traces.txt')
#get_result('results_rocketship')
#gen_binaries()
#launch_runs('rocketship-hysterisis-maxpsel')
#get_results('rocketship-hysterisis-maxpsel')
#genplots()
parser = argparse.ArgumentParser()
parser.add_argument('--launchrun', default=None)
parser.add_argument('--tracelist', default='alltraces.txt')
parser.add_argument('--getresult', default=None)
parser.add_argument('--plot', default=None)
parser.add_argument('--plotdatadir', default=None)
parser.add_argument('--genbin', default=None, action='store_true')
parser.add_argument('--plotbox')
args = parser.parse_args()
if args.genbin is not None:
    gen_binaries()
if args.launchrun is not None:
    launch_run(args.launchrun, tracelist=args.tracelist)
    get_result('results_' + args.launchrun)
if args.getresult is not None:
    get_result(args.getresult)
if args.plot is not None:
    if args.plotdatadir is None:
        raise RuntimeError('--plotdatadir not specified!')
    plot(args.plot, args.plotdatadir)
plotbox()
