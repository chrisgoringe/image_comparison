from modules.scoring import ImageDatabase
import scipy
import matplotlib.pyplot as plt
import os, argparse

def parse_arguments():
    parser = argparse.ArgumentParser("Compare a series of scorefiles")
    parser.add_argument('-d', '--directory', help="Top level directory", required=True)
    parser.add_argument('-n', '--no_plot', action="store_true", help="Don't show a graph")
    parser.add_argument('-s', '--scores', default="scores.json", help="Filename of scores file (relative to top level directory)")
    parser.add_argument('-m', '--model_scorefile', help="Plot comparison with model scorefile")
    Args.namespace = parser.parse_args()

class Args:
    namespace = None
    @classmethod
    def __getattribute__(cls, attr):
        if hasattr(cls.namespace, attr): return cls.namespace.attr
        if attr=='model_scorefile': return False
        if attr=='plot': return not cls.namespace.no_plot
        raise Exception(f"Don't know about {attr}")
    
class Cache:
    cache = {}
    @classmethod
    def get(cls, a):
        if not a in cls.cache:
            id = ImageDatabase(Args.directory,a)
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
    for f in os.listdir(Args.directory):
        if os.path.splitext(f)[1]==".json":
            if f.startswith(os.path.splitext(Args.scores)[0]+"_"): 
                number = int(os.path.splitext(f)[0][len(os.path.splitext(Args.score)[0])+1:])
                nf.append((number, f))
    nf.sort()
    return tuple(f for _,f in nf), tuple(n for n,_ in nf)

if __name__=="__main__":
    parse_arguments()
    files, numbers = find_numbered_files()

    if Args.model_scorefile:
        print("\n Comparison with model predictions")
        data = compare((Args.model_scorefile,)+ files)
        if Args.plot: plt.plot(numbers, data)
    
    print("\n Comparisons with previous database")
    data = list(compare(files[i:i+2])[0] for i in range(len(files)-1))
    if Args.plot: plt.plot(numbers[1:],  data )

    if Args.plot: plt.show()