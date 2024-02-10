import random, math, time
import customtkinter
import scipy

class Args:
# The directory where the images are (subfolders are included)
    top_level_image_directory = r"C:\Users\chris\Documents\GitHub\ComfyUI_windows_portable\ComfyUI\output\training4"
# How strongly to prefer images that have been shown less. 0 = totally random, 0.999 = very very strong preference. 0.4 is fine.
    low_count_weight =  0.4
# Preferred height of the window on your screen  
    height = 768
# How many comparisons to do each time you run the script. 
    max_comparisons = 100
# How many images to compare each time. Strongly suggest you leave as 2.
    image_count = 2
# List the highest rated n images at the end (0 or None for off)
    show_top_n = 10
# how rapidly to update scores. k = 0.7 has some theoretical basis!
    k = 0.7
    weight_k_by_speed = False
    default_seconds = 1.2
    weighting_limits = (0.5, 2.0)

# Scores file (in the top_level_image_directory) to load from. Set to "" or None to start without any scores.
    load_from = "start_from_model.json"
# Name under which to save the scores at the end. An additional file, `same_name_x.json` (where x is number of comparisons to date) is also saved.
    score_filename = "start_from_model.json"
# Save a csv file as well?
    csv_filename = None

from modules.scoring import ImageDatabase, ImageRecord, ScoreUpdater

def clamp(n, min, max): 
    if n < min: return min
    elif n > max: return max
    else: return n 

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
        self.database = ImageDatabase(Args.top_level_image_directory, loadfrom=Args.load_from)

        self.database.sort(reverse=True)
        self.start_order = { f:i for i,f in enumerate(self.database.image_records) }

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

        self.starttime = time.monotonic()
        

    def pick_images(self):
        self.image_records = self.image_chooser.pick_images(Args.image_count)
        for i, image_record in enumerate(self.image_records):
            im = self.database.get_image(image_record)
            try:
                self.image_labels[i].configure(image = customtkinter.CTkImage(light_image=im, size=(int(Args.height*im.width/im.height),Args.height)))
            except:
                print(image_record)
        self.lasttime = time.monotonic()

    def keyup(self,k):
        if k.char in "123456789"[:Args.image_count+1]: 
            time_taken = time.monotonic() - self.lasttime
            k_fac = clamp(Args.default_seconds / time_taken, *Args.weighting_limits) if Args.weight_k_by_speed else 1.0
            win = int(k.char)-1
            for i in range(Args.image_count):
                if i!=win: self.score_updater.update_scores(winner = self.image_records[win], loser=self.image_records[i], k_fac=k_fac)
            self.count += 1
            self.pick_images()
        if self.count>=Args.max_comparisons or k.char=='q':
            self.database.sort(reverse=True)
            self.database.save_scores(Args.score_filename)
            if Args.csv_filename: self.database.save_csv(Args.csv_filename)
            if Args.show_top_n: print("\n".join((ir.printable for ir in self.database.records[:Args.show_top_n])))
            summary = self.database.printable + " " + self.score_updater.printable
            print(summary)
            with open('summary.txt','a') as f: print(summary,file=f)
            print("{:>6.3f} s/image".format((time.monotonic()-self.starttime)/self.count))

            spearman = scipy.stats.spearmanr([ self.start_order[f] for f in self.start_order ],
                                             [ self.start_order[f] for f in self.database.image_records ])
            print("spearman correlation start to end of run: {:>6.4f}".format(spearman.statistic))
            self.app.quit()
        self.app.title("{:>4}/{:<4} {:>6.3f} s/image".format(self.count, Args.max_comparisons, (time.monotonic()-self.starttime)/self.count))

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
    
