from archlib import Analyzer, LaunchExperiment

def get_results():
    analyzer = Analyzer('results_2mb_noprefetch_lru')
    analyzer.gencsv("results_2mb_noprefetch_lru.csv")

    analyzer = Analyzer('results_2mb_noprefetch_shippp')
    analyzer.gencsv("results_2mb_noprefetch_shippp.csv")

    analyzer = Analyzer('results_2mb_noprefetch_hawkeye')
    analyzer.gencsv("results_2mb_noprefetch_hawkeye.csv")

def launch_runs():
    r = LaunchExperiment(binary='champsim-llc-2mb-noprefetch-shippp-maxrrpv-4', 
                        bindir='bin',
                        warmup_inst= 10000000,
                        simulation_inst= 100000000,
                        tracelist='alltraces.txt',
                        tracedir='CRC2_traces',
                        batchsize=8)
    r.run()

launch_runs()
