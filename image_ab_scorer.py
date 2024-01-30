import dataclasses
import os, json, random, math, threading, time
from PIL import Image
import customtkinter

class Args:
    top_level_image_directory = r"C:\Users\chris\Documents\GitHub\ComfyUI_windows_portable\ComfyUI\output\training"
    # How strongly to prefer images that have been shown less. 0 = totally random, 0.999 = very very strong preference. Weight is (1-lcw)^(-comparisons)
    low_count_weight =  0.4 
    # Preferred height of the window on your screen  
    height = 800
    # How many comparisons to do
    max_comparisons = 100
    # How many images to compare each time
    image_count = 2
    # Show top n at the end (0 for off)
    show_top_n = 10
    # how rapidly to update scores 
    k = 0.7
    # reload scores from previous runs
    reload_if_available = True

    score_filename = "image_scores.json"
    csv_filename = "image_scores.csv"

    # experimental/testing - leave False
    one_pass = False
    automate = False


@dataclasses.dataclass
class ImageRecord:
    relative_filepath:str
    comparisons:int = 0
    score:float = 0

    @property
    def printable(self):
        return f"'{self.relative_filepath}',"+"{:>6.3f},{:>4}".format(self.score, self.comparisons)
    
    def __hash__(self):
        return self.relative_filepath.__hash__()

class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        return super().default(o)

class ImageDatabase:
    def __init__(self, base_directory, load=True, add_files=True, remove_files=True):
        self.base_directory = base_directory
        self.image_records:dict[str, ImageRecord] = {}
        self.metadata:dict = {}
        if load: self.load_scores()
        if add_files: self.recursively_add()
        if remove_files: self.remove_missing()

    def load_scores(self, filename=Args.score_filename):
        scores_path = os.path.join(self.base_directory,filename)
        if os.path.exists(scores_path):
            with open(scores_path,'r') as f:
                loaded:dict = json.load(f)
                self.image_records = loaded.get('ImageRecords',[])
                for ir in self.image_records: self.image_records[ir] = ImageRecord(**self.image_records[ir])
                self.metadata = loaded.get('Metadata', {})

    def save_scores(self, filename=Args.score_filename):
        scores_path = os.path.join(self.base_directory,filename)
        with open(scores_path,'w') as f:
            print(json.dumps({"ImageRecords":self.image_records, "Metadata":self.metadata}, indent=2, cls=EnhancedJSONEncoder), file=f)

    def save_csv(self, filename=Args.csv_filename):
        scores_path = os.path.join(self.base_directory,filename)
        with open(scores_path,'w') as f:
            for relative_path in self.image_records:
                image_record:ImageRecord = self.image_records[relative_path]
                print(image_record.printable, file=f)

    def sort(self, reverse=False):
        l = [self.image_records[x] for x in self.image_records]
        l.sort(key=lambda ir:ir.score, reverse=reverse)
        self.image_records = {ir.relative_filepath:ir for ir in l}

    def recursively_add(self):
        for (dir_path, dir_names, file_names) in os.walk(self.base_directory):
            rel_dir = os.path.relpath(dir_path, self.base_directory)
            for filename in file_names:
                relative_path = os.path.join(rel_dir,filename)
                if not relative_path in self.image_records:
                    fullpath = os.path.join(dir_path, filename)
                    try:
                        i = Image.open(fullpath)
                        self.image_records[relative_path] = ImageRecord(relative_path)
                    except:
                        pass

    def max_aspect_ratio(self):
        mar = 0
        for relative_path in self.image_records:
            i = Image.open(os.path.join(self.base_directory, relative_path))
            ar = i.width / i.height
            mar = max(mar, ar)
        return mar

    @property
    def records(self):
        return [self.image_records[r] for r in self.image_records]
    
    @property
    def total_comparisons(self):
        return sum(self.image_records[r].comparisons for r in self.image_records)
    
    @property
    def image_count(self):
        return len(self.image_records)
    
    @property
    def printable(self):
        return "{:>6} comparisons for {:>6} images.".format(self.total_comparisons, self.image_count)

    def remove_missing(self):
        missing = []
        for relative_path in self.image_records:
            try:
                i = Image.open(os.path.join(self.base_directory, relative_path))
            except:
                missing.append(relative_path)
        for missing_one in missing:
            self.image_records.pop(missing_one)

class ImageChooser:
    def __init__(self, image_records:list[ImageRecord], weighter:callable):
        self.image_records = image_records
        self.weighter = weighter

    def pick_images(self, number) -> list[ImageRecord]:
        weights = [self.weighter(x) for x in self.image_records]
        choices = random.choices(self.image_records, weights=weights, k=number)
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

class ScoreUpdater:
    def __init__(self, k):
        self.k = k
        self.total_comparisons = 0
        self.average_p = 0
        self.average_bestp = 0
        self.total_favourite_wins = 0

    def update_scores(self, winner:ImageRecord, loser:ImageRecord):
        delta = winner.score - loser.score
        p = 1.0/(1.0+math.pow(10,-delta))
        winner.score += (1-p) * self.k
        loser.score -= (1-p) * self.k
        winner.comparisons += 1
        loser.comparisons += 1
        self.average_p = (self.total_comparisons * self.average_p + p)/(self.total_comparisons + 1)
        self.average_bestp = (self.total_comparisons * self.average_bestp + max(p,1-p))/(self.total_comparisons + 1)
        self.total_favourite_wins += (p>0.5)
        self.total_comparisons += 1

    @property
    def printable(self):
        return "Average p value for chosen result {:>6.4f}%. Average bestp {:>6.4f}%. Choice matched {:>6.4f}%.".format(
                self.average_p * 100, self.average_bestp * 100, self.total_favourite_wins * 100 / self.total_comparisons )
    
class OnePassScoreUpdater:
    def __init__(self,records:list[ImageRecord]):
        for r in records: 
            r.unknowns = set([r2 for r2 in records if r!=r2])
            r.above = set()
        self.records = records

    def update_scores(self, winner:ImageRecord, loser:ImageRecord):
        assert winner in loser.unknowns and loser in winner.unknowns
        winner.above.add(loser)
        winner.unknowns.remove(loser)
        loser.unknowns.remove(winner)
        for third in self.records:
            if third in loser.above and third in winner.unknowns:
                self.update_scores(winner, third)
            if winner in third.above and loser in third.unknowns:
                self.update_scores(third, loser)

        winner.score = len(winner.above)

    @property
    def total_left(self):
        return sum(len(r.unknowns) for r in self.records)
    
    @property
    def printable(self):
        return "{:>6} unknowns for {:>5} images.".format(self.total_left, len(self.records))

class OnePassImageChooser:
    def __init__(self, image_records:list[ImageRecord]):
        self.image_records = image_records

    def pick_images(self, number) -> list[ImageRecord]:
        weights = [1/len(x.unknowns) if x.unknowns else 0 for x in self.image_records]
        choice1 = random.choices(self.image_records, weights=weights, k=1)[0]
        weights = [len(x.unknowns) for x in choice1.unknowns]
        choice2 = random.choices(list(choice1.unknowns), weights=weights, k=1)[0]
        return (choice1, choice2)
    
    @classmethod
    def from_database(cls, database:ImageDatabase):
        return OnePassImageChooser(database.records)

class TheApp:
    def __init__(self):
        self.app = customtkinter.CTk()
        self.app.title("H.A.S.")
        self.database = ImageDatabase(Args.top_level_image_directory, load=Args.reload_if_available)
        print(f"Comparing {len(self.database.records)} images")
        assert len(self.database.records) >= 2
        if Args.one_pass:
            self.image_chooser = OnePassImageChooser.from_database(self.database)
            self.score_updater = OnePassScoreUpdater(self.database.records)
        else:
            self.image_chooser = ImageChooser.from_database(self.database, low_count_weight=Args.low_count_weight)
            self.score_updater = ScoreUpdater(Args.k)
        self.count = 0

        maw = self.database.max_aspect_ratio()
        self.app.geometry(f"{Args.height*maw*Args.image_count}x{Args.height}")
        self.image_labels = [customtkinter.CTkLabel(self.app, text="") for _ in range(Args.image_count)]
        for i, label in enumerate(self.image_labels):
            label.grid(row=0, column=2*i)
            if i: self.app.grid_columnconfigure(2*i-1, weight=1)

        self.app.bind("<KeyRelease>", self.keyup)
        self.pick_images()

        if Args.automate:
            class M:
                def __init__(self):
                    self.char = ""

            def dorandom():
                k = M()
                while(True):
                    k.char = "1" if random.random()>0.5 else "2"
                    self.keyup(k)
                    time.sleep(0.1)
            self.t = threading.Thread(target = dorandom, daemon=True)
            self.t.start()

    def pick_images(self):
        self.image_records = self.image_chooser.pick_images(Args.image_count)
        if not Args.automate:
            for i, image_record in enumerate(self.image_records):
                im = Image.open(os.path.join(Args.top_level_image_directory, image_record.relative_filepath))
                self.image_labels[i].configure(image = customtkinter.CTkImage(light_image=im, size=(int(Args.height*im.width/im.height),Args.height)))

    def keyup(self,k):
        if k.char in "123456789"[:Args.image_count+1]: 
            win = int(k.char)-1
            for i in range(Args.image_count):
                if i!=win: self.score_updater.update_scores(winner = self.image_records[win], loser=self.image_records[i])
            self.count += 1
            if not (Args.one_pass and self.score_updater.total_left==0):
                self.pick_images()
        if (self.count==Args.max_comparisons and not Args.one_pass) or k.char=='q' or (Args.one_pass and self.score_updater.total_left==0):
            self.database.sort(reverse=True)
            self.database.save_scores()
            self.database.save_csv()
            if Args.show_top_n: print("\n".join((ir.printable for ir in self.database.records[:Args.show_top_n])))
            summary = self.database.printable + " " + self.score_updater.printable
            print(summary)
            with open('summary.txt','a') as f: print(summary,file=f)
            self.app.quit()
        if self.count % 10 == 0:
            print(self.count)
            if Args.one_pass: print(self.score_updater.printable)

def main():
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
    
