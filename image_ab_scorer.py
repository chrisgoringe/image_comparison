import dataclasses
import os, json, random, math
from PIL import Image
import customtkinter

class Args:
    top_level_image_directory = r"C:\Users\chris\Documents\GitHub\ComfyUI_windows_portable\ComfyUI\output\compare"
    # How strongly to prefer images that have been shown less. 0 = totally random, 0.999 = very very strong preference. Weight is (1-lcw)^(-comparisons)
    low_count_weight =  0.4 
    # Preferred height of the window on your screen  
    height = 800
    # tell me how many images have fewer than this number of comparisons at the end
    threshold = 5
    # How many comparisons to do
    max_comparisons = 10
    # How many images to compare each time
    image_count = 2
    # Show top n at the end (0 for off)
    show_top_n = 10
    # how rapidly to update scores 
    k = 0.7
    # reload scores from previous runs
    reload_if_available = False


@dataclasses.dataclass
class ImageRecord:
    relative_filepath:str
    comparisons:int = 0
    score:float = 0

    @property
    def printable(self):
        return f"'{self.relative_filepath}',"+"{:>6.3f},{:>4}".format(self.score, self.comparisons)

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

    def load_scores(self, filename="image_scores.json"):
        scores_path = os.path.join(self.base_directory,filename)
        if os.path.exists(scores_path):
            with open(scores_path,'r') as f:
                loaded:dict = json.load(f)
                self.image_records = loaded.get('ImageRecords',[])
                for ir in self.image_records: self.image_records[ir] = ImageRecord(**self.image_records[ir])
                self.metadata = loaded.get('Metadata', {})

    def save_scores(self, filename="image_scores.json"):
        scores_path = os.path.join(self.base_directory,filename)
        with open(scores_path,'w') as f:
            print(json.dumps({"ImageRecords":self.image_records, "Metadata":self.metadata}, indent=2, cls=EnhancedJSONEncoder), file=f)

    def save_csv(self, filename="image_scores.csv"):
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

    @staticmethod
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

    def update_scores(self, winner:ImageRecord, loser:ImageRecord):
        delta = winner.score - loser.score
        p = 1.0/(1.0+math.pow(10,-delta))
        winner.score += (1-p) * self.k
        loser.score -= (1-p) * self.k
        winner.comparisons += 1
        loser.comparisons += 1
        self.average_p = (self.total_comparisons * self.average_p + p)/(self.total_comparisons + 1)
        self.total_comparisons += 1

class TheApp:
    def __init__(self):
        self.app = customtkinter.CTk()
        self.app.title("H.A.S.")
        self.database = ImageDatabase(Args.top_level_image_directory, load=Args.reload_if_available)
        print(f"Comparing {len(self.database.records)} images")
        assert len(self.database.records) >= 2
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

    def pick_images(self):
        self.image_records = self.image_chooser.pick_images(Args.image_count)
        for i, image_record in enumerate(self.image_records):
            im = Image.open(os.path.join(Args.top_level_image_directory, image_record.relative_filepath))
            self.image_labels[i].configure(image = customtkinter.CTkImage(light_image=im, size=(int(Args.height*im.width/im.height),Args.height)))

    def keyup(self,k):
        if k.char in "123456789"[:Args.image_count+1]: 
            win = int(k.char)-1
            for i in range(Args.image_count):
                if i!=win: self.score_updater.update_scores(winner = self.image_records[win], loser=self.image_records[i])
            self.count += 1
            self.pick_images()
        if self.count==Args.max_comparisons or k.char=='q':
            self.database.sort(reverse=True)
            self.database.save_scores()
            self.database.save_csv()
            if Args.show_top_n: print("\n".join((ir.printable for ir in self.database.records[:Args.show_top_n])))
            summary = "{:>6} comparisons. Average p value for chosen result {:>6.4f}%".format(self.database.total_comparisons, self.score_updater.average_p * 100)
            print(summary)
            with open('summary.txt','a') as f: print(summary,file=f)
            self.app.quit()
        if self.count % 10 == 0:
            print(self.count)

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
    
