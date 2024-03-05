from modules.scoring import ImageDatabase
import scipy
import matplotlib.pyplot as plt
import os, argparse, time

class CommentArgumentParser(argparse.ArgumentParser):
    def convert_arg_line_to_args(self, arg_line):
        if arg_line.startswith('#'): return [] 
        line = "=".join(a.strip() for a in arg_line.split('='))
        return [line,] if len(line) else []

def parse_arguments():
    global args
    parser = CommentArgumentParser("Score a set of images by a series of AB comparisons", fromfile_prefix_chars='@')
    parser.add_argument('-d', '--directory', help="Top level directory", required=True)
    parser.add_argument('-n', '--no_plot', action="store_true", help="Don't show a graph")
    parser.add_argument('-s', '--scores', default="scores.csv", help="Filename of scores file (relative to top level directory)")
    parser.add_argument('-m', '--model_scorefile', help="Plot comparison with model scorefile")
    args, unknown = parser.parse_known_args()
    if unknown: print(f"Ignoring unknown arguments {unknown}")
    
class Cache:
    cache = {}
    @classmethod
    def get(cls, a):
        if not a in cls.cache:
            id = ImageDatabase(args.directory,loadfrom=a,add_files=False,remove_files=False)
            id.sort()
            cls.cache[a] = { f : i for i,f in enumerate(id.image_records) }
        return cls.cache[a]

def compare(files):
    ranks = list(Cache.get(a) for a in files)
    results = []
    for rank_b, name_b in zip(ranks, files):
        if name_b!=files[0]:
            results.append(_compare(ranks[0],rank_b,files[0][:-5],name_b[:-5]))
    return results

def _compare(rank_map_a,rank_map_b,name_a,name_b) -> float:
    ranks_a = [ rank_map_a[f] for f in rank_map_a ]
    ranks_b = [ rank_map_b[f] for f in rank_map_a ]

    spearman = scipy.stats.spearmanr(ranks_a,ranks_b)
    print("{:>30} v {:<30} spearman {:>6.4f} (p={:>8.2})".format(name_a, name_b, spearman.statistic, spearman.pvalue))
    return spearman.statistic

def find_numbered_files():
    nf = []
    for f in os.listdir(args.directory):
        if os.path.splitext(f)[1]==".csv":
            if f.startswith(os.path.splitext(args.scores)[0]+"_"): 
                number = int(os.path.splitext(f)[0][len(os.path.splitext(args.scores)[0])+1:])
                nf.append((number, f))
    nf.sort()
    return tuple(f for _,f in nf), tuple(n for n,_ in nf)

if __name__=="__main__":
    parse_arguments()
    files, numbers = find_numbered_files()

    if args.model_scorefile:
        print("\n Comparison with model predictions")
        data = compare((args.model_scorefile,)+ files)
        if not args.no_plot: plt.plot(numbers, data)
    
    print("\n Comparisons with previous database")
    data = list(compare(files[i:i+2])[0] for i in range(len(files)-1))
    if not args.no_plot:
        plt.plot(numbers[1:],  data )
        plt.show()
        while(True): time.sleep(1)