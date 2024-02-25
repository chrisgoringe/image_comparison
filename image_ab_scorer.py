import random, math, time, argparse
import customtkinter
import scipy

from modules.scoring import ImageDatabase, ImageRecord, ScoreUpdater

class CommentArgumentParser(argparse.ArgumentParser):
    def convert_arg_line_to_args(self, arg_line):
        if arg_line.startswith('#'): return [] 
        line = "=".join(a.strip() for a in arg_line.split('='))
        return [line,] if len(line) else []

def parse_arguments():
    to_string_list = lambda s : list( x.strip() for x in s.split(',') )

    parser = CommentArgumentParser("Score a set of images by a series of AB comparisons", fromfile_prefix_chars='@')
    parser.add_argument('-d', '--directory', help="Top level directory", required=True)
    parser.add_argument('-s', '--scores', default="scores.json", help="Filename of scores file (relative to top level directory) from which scores are loaded (if present) and saved")
    parser.add_argument('-r', '--restart', action="store_true", help="Force a restart (don't reload scores file even if present)")
    parser.add_argument('-c', '--csvfile', help="Save scores as a csv in this file (relative to top level directory) as well as in the scores file")
    parser.add_argument('-t', '--trust', type=to_string_list, help="Comma separated list of extensions that are trusted to be images (eg -t=.jpg,.png)")

    parser.add_argument('--lcw', type=float, default=0.4, help="Weighting priority towards less frequently compared images (0-0.99)")
    parser.add_argument('--height', type=int, default=768, help="Height of window")
    parser.add_argument('--number', type=int, default=100, help="Number of sets of images to compare")
    parser.add_argument('--number_to_compare', type=int, default=2, help="Number of images to choose from")

    parser.add_argument('--k', type=float, default=0.7, help="K value for score updates")
    parser.add_argument('--weight_by_speed', action="store_true", help="Weight fast responses more (see also --default_seconds, --weight_min, --weight_max)")
    parser.add_argument('--default_seconds', type=float, default=1.5, help="Typical response time (requires --weight_by_speed)")
    parser.add_argument('--weight_min', type=float, default=0.5, help="Minimum weighting for slow responses (requires --weight_by_speed)")
    parser.add_argument('--weight_max', type=float, default=2, help="Maximum weighting for fase responses (requires --weight_by_speed)")

    Args.namespace = parser.parse_args()
    print(Args.namespace)

class _Args(object):
    def __init__(self):
        self.namespace = None

    def __getattr__(self, attr):
        if hasattr(self.namespace, attr): return getattr(self.namespace,attr)
        if attr=='load_from': return None if self.namespace.restart else self.namespace.scores
        raise KeyError(attr)
    
Args = _Args()

def clamp(n, min, max): return min if n < min else (max if n > max else n)

class ImageChooser:
    def __init__(self, image_records:list[ImageRecord], weighter:callable):
        self.image_records = image_records
        self.weighter = weighter

    def pick_images(self, number) -> list[ImageRecord]:
        weights = [self.weighter(x) for x in self.image_records]
        choices = random.choices(self.image_records, weights=weights, k=number-1)
        choices.append(random.choice(self.image_records))
        for i,c in enumerate(choices):
            if c in choices[i+1:]:
                return self.pick_images(number)
        return choices
    
    @classmethod
    def from_database(cls, database:ImageDatabase, weighter:callable=None, low_count_weight:float=None):
        weighter = weighter or cls.weighter(low_count_weight)
        return ImageChooser(database.records, weighter)

    @classmethod
    def weighter(cls, low_count_weight=0.0):
        if low_count_weight:
            def lcw(ir:ImageRecord):
                return math.pow(1-low_count_weight,ir.comparisons)
            return lcw
        return lambda a:1.0

class TheApp:
    def __init__(self):
        self.app = customtkinter.CTk()
        self.app.title("")
        self.database = ImageDatabase(Args.directory, loadfrom=Args.load_from, trust_extensions=Args.trust)

        self.database.sort(reverse=True)
        self.start_order = { f:i for i,f in enumerate(self.database.image_records) }

        print(f"Comparing {len(self.database.records)} images")
        assert len(self.database.records) >= 2
        self.image_chooser = ImageChooser.from_database(self.database, low_count_weight=Args.lcw)
        self.score_updater = ScoreUpdater(Args.k)
        self.count = 0

        maw = self.database.max_aspect_ratio()
        self.app.geometry(f"{Args.height*maw*Args.number_to_compare}x{Args.height}")
        self.image_labels = [customtkinter.CTkLabel(self.app, text="") for _ in range(Args.number_to_compare)]
        for i, label in enumerate(self.image_labels):
            label.grid(row=0, column=2*i)
            if i: self.app.grid_columnconfigure(2*i-1, weight=1)

        self.app.bind("<KeyRelease>", self.keyup)
        self.pick_images()

        self.starttime = time.monotonic()
        

    def pick_images(self):
        self.image_records = self.image_chooser.pick_images(Args.number_to_compare)
        for i, image_record in enumerate(self.image_records):
            im = self.database.get_image(image_record)
            try:
                self.image_labels[i].configure(image = customtkinter.CTkImage(light_image=im, size=(int(Args.height*im.width/im.height),Args.height)))
            except:
                print(image_record)
        self.lasttime = time.monotonic()

    def keyup(self,k):
        if k.char in "123456789"[:Args.number_to_compare+1]: 
            time_taken = time.monotonic() - self.lasttime
            k_fac = clamp(Args.default_seconds / time_taken, Args.weight_min, Args.weight_max) if Args.weight_by_speed else 1.0
            win = int(k.char)-1
            for i in range(Args.number_to_compare):
                if i!=win: self.score_updater.update_scores(winner = self.image_records[win], loser=self.image_records[i], k_fac=k_fac)
            self.count += 1
            self.pick_images()
        if self.count>=Args.number or k.char=='q':
            self.database.sort(reverse=True)
            if Args.scores.endswith("csv"): self.database.save_csv(Args.scores)
            else: self.database.save_scores(Args.scores)
            if Args.csvfile: self.database.save_csv(Args.csvfile)

            summary = self.database.printable + " " + self.score_updater.printable
            print(summary)
            with open('summary.txt','a') as f: print(summary,file=f)
            print("{:>6.3f} s/image".format((time.monotonic()-self.starttime)/self.count))

            spearman = scipy.stats.spearmanr([ self.start_order[f] for f in self.start_order ],
                                             [ self.start_order[f] for f in self.database.image_records ])
            print("spearman correlation start to end of run: {:>6.4f}".format(spearman.statistic))
            self.app.quit()
        self.app.title("{:>4}/{:<4} {:>6.3f} s/image".format(self.count, Args.number, (time.monotonic()-self.starttime)/self.count))

def main():
    parse_arguments()
    a = TheApp()
    a.app.mainloop()
    hist = [0]*1000
    max_c = 0
    for r in a.database.records: 
        hist[r.comparisons] += 1
        max_c = max(max_c, r.comparisons)

    for i in range(max_c+1):
        print("{:>4} images have {:>4} comparisons".format(hist[i],i))

if __name__=="__main__":
    main()
    
