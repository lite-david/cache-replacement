from typing import List, Dict, Callable
import subprocess
import os
import csv
import time
import pandas as pd
from matplotlib import pyplot as plt
from scipy import stats
import json

class HarryPlotter:
    def __init__(self):
        self.metrics = {
            'ipc':[],
            'l2_latency':[],
            'mpki':[]
        }
        self.data = {}
        self.schmoo_param = None
    
    def plotmetric(self, metric:str):
        x = [xy[0] for xy in self.metrics[metric]]
        y = [xy[1] for xy in self.metrics[metric]]
        plt.plot(x, y, marker='o')
        plt.rc('font', size=15) 
        plt.xlabel(self.schmoo_param)
        plt.ylabel(metric)
        plt.show()

    def plotmetrics(self, metrics:list):
        plt.rc('font', size=14) 
        fig, ax = plt.subplots(len(metrics), 1)
        for i,metric in enumerate(metrics):
            x = [xy[0] for xy in self.metrics[metric]]
            y = [xy[1] for xy in self.metrics[metric]]
            ax[i].plot(x, y, 'o-')
            ax[i].set_ylabel(metric)
        
        ax[-1].set_xlabel(self.schmoo_param)
        plt.show()

    def agg(self, csvs: list, schmoo_param:str):
        self.schmoo_param = schmoo_param
        for csv in csvs:
            schmoo_val = csv.split('.csv')[0].split('-')[-1]
            df = pd.read_csv(f'{csv}')
            ipc = stats.gmean(df.iloc[:,1])
            l2_latency = float(df[['L2C AVERAGE MISS LATENCY']].mean())
            mpki_df = df[['LLC TOTAL MISS']]/100000
            mpki = float(mpki_df.mean())
            #mpki = stats.gmean(df.iloc[:,5]/100000)
            self.metrics['ipc'].append((int(schmoo_val), ipc))
            self.metrics['l2_latency'].append((int(schmoo_val), l2_latency))
            self.metrics['mpki'].append((int(schmoo_val), mpki))
        for k,v in self.metrics.items():
            v.sort()

    def load(self, csvs:list, columns:list, names:list):
        for csv,name in zip(csvs, names):
            df = pd.read_csv(f'{csv}')
            df = df[columns]
            self.data[name] = df

    def plotboxplot(self, names:list, column:str, showfliers=True):
        x = [self.data[name][column].values.tolist() for name in names]
        plt.boxplot(x, labels=names, showfliers=showfliers)
        plt.rc('font', size=15) 
        plt.ylabel(column)
        plt.show()




class LaunchExperiment:
    def __init__(self, binary: str, bindir:str, warmup_inst:int, simulation_inst:int, tracelist:str, tracedir:str, batchsize:int):
        self.binary = binary
        self.bindir = bindir
        self.warmup_inst = warmup_inst
        self.simulation_inst = simulation_inst
        self.tracelist = tracelist
        self.batchsize = batchsize
        self.tracedir = tracedir

    def run(self):
        # create a directory for the results for the binary
        results_dir = f'results_{self.binary}'
        os.makedirs(results_dir, exist_ok=True)
        base_cmd = [self.bindir + '/' + self.binary,
                    "--warmup_instructions", str(self.warmup_inst),
                    "--simulation_instructions", str(self.simulation_inst),
                    "--trace"]
        with open(self.tracelist, "r") as f:
            traces = f.readlines()
        traces = [x.strip() for x in traces]
        processes = []
        files = []
        inflight = 0
        try:
            for trace in traces:
                cmd = base_cmd + [self.tracedir + "/" + trace]
                if os.path.exists(f'{results_dir}/{trace}.txt'):
                    print(f'File exists, skipping {results_dir}/{trace}.txt')
                    continue
                with open(f'{results_dir}/{trace}.txt', "w") as f:
                    print(" ".join(cmd))
                    processes.append(subprocess.Popen(cmd, stdout=f, stderr=f))
                    files.append(f'{results_dir}/{trace}.txt')
                inflight += 1
                completed = []
                while inflight == self.batchsize:
                    time.sleep(2)
                    for i,p in enumerate(processes):
                        if p.poll() is not None:
                            completed.append(i)
                    inflight = inflight - len(completed)
                for i in completed:
                    del processes[i]
                    del files[i]
            for p in processes:
                p.wait()
        except KeyboardInterrupt:
            print("Received interrupt, killing processes & cleaning up")
            for i,p in enumerate(processes):
                os.remove(files[i])




class Analyzer:
    def __init__(self, resultsdir):
        self.resultsdir = resultsdir
        self.searchstrs = ["CPU 0 cumulative IPC",
                     "cpu0_L2C AVERAGE MISS LATENCY",
                     "LLC TOTAL",
                     "LLC LOAD",
                     "LLC RFO",
                     "LLC WRITEBACK",
                     "LLC TRANSLATION",
                     "LLC AVERAGE MISS LATENCY",
                     ]

        self.cols = ["Cumulative IPC",
                     "L2C AVERAGE MISS LATENCY",
                     "LLC TOTAL ACCESS",
                     "LLC TOTAL HIT",
                     "LLC TOTAL MISS",
                     "LLC LOAD ACCESS",
                     "LLC LOAD HIT",
                     "LLC LOAD MISS",
                     "LLC RFO ACCESS",
                     "LLC RFO HIT",
                     "LLC RFO MISS",
                     "LLC WRITEBACK ACCESS",
                     "LLC WRITEBACK HIT",
                     "LLC WRITEBACK MISS",
                     "LLC TRANSLATION ACCESS",
                     "LLC TRANSLATION HIT",
                     "LLC TRANSLATION MISS",
                     "LLC AVERAGE MISS LATENCY"
                     ]

    def gencsv(self, output_file = "results.csv"):
        files = os.listdir(self.resultsdir)
        with open(output_file, "w", newline='') as csvfile:
            csvwriter = csv.writer(csvfile, delimiter=",", quotechar='|', quoting=csv.QUOTE_MINIMAL)
            csvwriter.writerow(["benchmark"] + self.cols)
            for file in files:
                row = [file.split('.')[0]]
                with open(self.resultsdir + "/" + file, "r") as f:
                    lines = f.readlines()
                for line in lines:
                    for i,searchstr in enumerate(self.searchstrs):
                        if line.startswith(searchstr):
                            if i < 2 or i == 7:
                                val = line.split(':')[1].split()[0]
                                row.append(val)
                            else:
                                val = line.split()
                                row.append(val[3])
                                row.append(val[5])
                                row.append(val[7])
                            break

                csvwriter.writerow(row)


class Experiment:
    def __init__(self, config: str):
        with open(config, 'r') as f:
            self.config = json.load(f)

    def compile_bin(self):
        with open('tmpconfig.json', 'w', encoding='utf-8') as f:
            json.dump(self.config, f)
        cmd = ['./config.sh', 'tmpconfig.json']
        p = subprocess.Popen(cmd)
        p.wait()
        cmd = ['make']
        p = subprocess.Popen(cmd)
        p.wait()
