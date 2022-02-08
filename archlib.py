from typing import List, Dict, Callable
import subprocess
import os
import csv


class LaunchExperiment:
    def __init__(self, experiments: List, tracelist: str, args: str, batchsize: int = 16, sleep: int = 6):
        self.experiments = experiments
        self.tracelist = tracelist
        self.args = args
        self.batchsize = batchsize
        self.sleep = sleep

    def run(self):
        pass


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

        self.cols = ["CPU 0 cumulative IPC",
                     "cpu0_L2C AVERAGE MISS LATENCY",
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
                     "LLC AVERAGE MISS LATENCY",
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
    def __init__(self,
                 name: str,
                 variables: Dict = None,
                 src_paths: List = None,
                 buildfn: Callable[[str], None] = None):
        self.name = name
        self.variables = variables
        self.src_paths = src_paths
        self.buildfn = buildfn
        self.schmoo_variables = None

    # store the files with lines that have schmoo@<varname>:<original_value>
    def registerSchmooVariables(self):
        self.schmoo_variables = dict()
        exp_vars = self.variables.keys()
        for src in self.src_paths:
            with open(src, 'r') as f:
                src_code = f.readlines()
            lines = [(i, line) for i, line in enumerate(src_code) if 'schmoo@' in line]
            for line in lines:
                line_number, code = line[0], line[1]
                varname_val = code.split('schmoo@')[1].split(':')
                if len(varname_val) != 2:
                    raise RuntimeError(f'Incorrectly formatted schmoo marker at line number {line[0]}:{line[1]}')
                if varname_val[0] in exp_vars:
                    vals = self.variables[varname_val[0]]
                    self.schmoo_variables[varname_val[0]] = {
                        'line_number': line_number,
                        'original_val': varname_val[1],
                        'schmoo_vals': vals,
                        'file': src,
                        'lim': len(vals) - 1,
                        'iter': 0
                    }

    def filemod(self, var):
        var_ds = self.schmoo_variables[var]
        line_number = var_ds['line_number']
        original_val = var_ds['original_val']
        if var_ds['iter'] > var_ds['lim']:
            var_ds['iter'] = 0
        new_val = var_ds['schmoo_vals'][var_ds['iter']]
        with open(var_ds['file'], 'r') as f:
            src_code = f.readlines()
        src_code[line_number].replace(original_val, str(new_val), 1)
        with open(var_ds['file'], 'w') as f:
            f.writelines(src_code)
        var_ds['iter'] += 1
        return var, str(new_val)

    # For each variable generate binaries with the specified values to schmoo
    def schmoo(self):
        experiments = []
        vars = self.schmoo_variables.keys()
        # stopping condition for permutation generation
        limit = self.schmoo_variables[vars[-1]['lim']]
        while self.schmoo_variables[vars[-1]]['iter'] != limit:
            exp_name = self.name
            for v in vars:
                var, val = self.filemod(v)
                exp_name += f'_{var}_{val}'
            self.buildfn(exp_name)
            experiments.append(exp_name)
        return experiments
