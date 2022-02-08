from archlib import Analyzer

analyzer = Analyzer('results_2mb_noprefetch_lru')
analyzer.gencsv("results_2mb_noprefetch_lru.csv")

analyzer = Analyzer('results_2mb_noprefetch_shippp')
analyzer.gencsv("results_2mb_noprefetch_shippp.csv")

analyzer = Analyzer('results_2mb_noprefetch_hawkeye')
analyzer.gencsv("results_2mb_noprefetch_hawkeye.csv")