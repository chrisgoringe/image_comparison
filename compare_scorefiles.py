from modules.scoring import ImageDatabase
import scipy
import matplotlib.pyplot as plt
import os

class Args:
    top_level_image_directory = r"C:\Users\chris\Documents\GitHub\ComfyUI_windows_portable\ComfyUI\output\training4"
    score_filename = "scores.json"
    plot_compare_with_previous = True

    model_score_filename = None
    plot_compare_with_model = False
    
class Cache:
    cache = {}
    dir = Args.top_level_image_directory

    @classmethod
    def get(cls, a):
        if not a in cls.cache:
            id = ImageDatabase(cls.dir,a)
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
    for f in os.listdir(Args.top_level_image_directory):
        if os.path.splitext(f)[1]==".json":
            if f.startswith(os.path.splitext(Args.score_filename)[0]+"_"): 
                number = int(os.path.splitext(f)[0][len(os.path.splitext(Args.score_filename)[0])+1:])
                nf.append((number, f))
    nf.sort()
    return tuple(f for _,f in nf), tuple(n for n,_ in nf)

if __name__=="__main__":
    files, numbers = find_numbered_files()

    if Args.model_score_filename:
        print("\n Comparison with model predictions")
        data = compare((Args.model_score_filename,)+ files)
        if Args.plot_compare_with_model: plt.plot(numbers, data)
    
    print("\n Comparisons with previous database")
    data = list(compare(files[i:i+2])[0] for i in range(len(files)-1))
    if Args.plot_compare_with_previous: plt.plot(numbers[1:],  data )

    if Args.plot_compare_with_model or Args.plot_compare_with_previous: 
        plt.show()