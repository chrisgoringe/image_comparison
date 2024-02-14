import os, math, json
from PIL import Image

class ImageRecord:
    def __init__(self,relative_filepath,comparisons=0,score=0.0):
        self.relative_filepath = os.path.normpath(relative_filepath)
        self.comparisons = comparisons
        self.score = score

    @property
    def printable(self):
        return f"'{self.relative_filepath}',"+"{:>6.3f},{:>4}".format(self.score, self.comparisons)
    
    @property
    def as_dictionary(self):
        return {"relative_filepath" : self.relative_filepath,
                "score" : self.score,
                "comparisons" : self.comparisons}
    
class ImageDatabase:
    def __init__(self, base_directory, loadfrom=None, add_files=True, remove_files=True, trust_extensions=[]):
        self.base_directory = base_directory
        self.image_records:dict[str, ImageRecord] = {}
        self.metadata:dict = {}
        if loadfrom: self.load_scores(loadfrom)
        if add_files: self.recursively_add(trust_extensions)
        if remove_files: self.remove_missing()

    def load_scores(self, filename):
        scores_path = os.path.join(self.base_directory,filename)
        if os.path.exists(scores_path):
            with open(scores_path,'r') as f:
                loaded:dict = json.load(f)
                self.image_records = loaded.get('ImageRecords',[])
                for ir in self.image_records: self.image_records[ir] = ImageRecord(**self.image_records[ir])
                self.metadata = loaded.get('Metadata', {})
        else:
            print(f"No scorefile to load at {scores_path}")

    @property
    def as_dictionary(self):
        return { "ImageRecords" : { f : self.image_records[f].as_dictionary for f in self.image_records },
                 "Metadata" : self.metadata }

    def save_scores(self, filename):
        self._save_scores(filename)
        self._save_scores(f"{os.path.splitext(filename)[0]}_{self.total_comparisons}.json")

    def _save_scores(self, filename):
        scores_path = os.path.join(self.base_directory,filename)
        with open(scores_path,'w') as f:
            print(json.dumps(self.as_dictionary, indent=2), file=f)

    def save_csv(self, filename):
        scores_path = os.path.join(self.base_directory,filename)
        with open(scores_path,'w') as f:
            for relative_path in self.image_records:
                image_record:ImageRecord = self.image_records[relative_path]
                print(image_record.printable, file=f)

    def sort(self, reverse=False):
        l = [self.image_records[x] for x in self.image_records]
        l.sort(key=lambda ir:ir.score, reverse=reverse)
        self.image_records = {ir.relative_filepath:ir for ir in l}

    def recursively_add(self, trust_extensions):
        for (dir_path, dir_names, file_names) in os.walk(self.base_directory):
            rel_dir = os.path.relpath(dir_path, self.base_directory)
            for filename in file_names:
                relative_path = os.path.relpath(os.path.join(rel_dir,filename))
                if not relative_path in self.image_records:
                    fullpath = os.path.join(dir_path, filename)
                    try:
                        if not os.path.splitext(fullpath)[1] in trust_extensions:
                            Image.open(fullpath)
                        self.image_records[relative_path] = ImageRecord(relative_path)
                    except:
                        pass

    def max_aspect_ratio(self) -> float:
        mar = 0
        for relative_path in self.image_records:
            i = Image.open(os.path.join(self.base_directory, relative_path))
            ar = i.width / i.height
            mar = max(mar, ar)
        return mar
    
    def get_image(self, ir:ImageRecord) -> Image:
        return Image.open(os.path.join(self.base_directory, ir.relative_filepath))

    @property
    def records(self) -> list[ImageRecord]:
        return [self.image_records[r] for r in self.image_records]
    
    @property
    def total_comparisons(self) -> int:
        return sum(self.image_records[r].comparisons for r in self.image_records)
    
    @property
    def image_count(self) -> int:
        return len(self.image_records)
    
    @property
    def printable(self) -> str:
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


class ScoreUpdater:
    def __init__(self, k):
        self.k = k
        self.total_comparisons = 0
        self.average_p = 0
        self.average_bestp = 0
        self.total_favourite_wins = 0

    def update_scores(self, winner:ImageRecord, loser:ImageRecord, k_fac = 1.0):
        delta = winner.score - loser.score
        p = 1.0/(1.0+math.pow(10,-delta))
        winner.score += (1-p) * k_fac * self.k
        loser.score -= (1-p) * k_fac * self.k
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