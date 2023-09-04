import customtkinter
import pyjson5, os, re, random, json, math, statistics
from PIL import Image
from options import *

def move_file(frompath, topath):
    i = 0
    split = os.path.splitext(topath)
    while os.path.exists(topath):
        i += 1
        topath=split[0]+f" ({i})"+split[1]
    os.rename(frompath, topath)

def main():
    for action in list(score_actions):
        if score_actions[action][:4]=="MOVE":
            dir = os.path.join(base,score_actions[action][5:])
            if not os.path.exists(dir):
                os.makedirs(dir)
            for key in action:
                score_actions[key] = lambda a : move_file(os.path.join(source_directory, a), os.path.join(dir, a))
        elif score_actions[action]=='DELETE':
            for key in action:
                score_actions[key] = lambda a : os.remove(os.path.join(source_directory,a))
        else:
            score_actions.pop(action)
   
    def extract_label(filename):
        return filename_extract_label.match(filename).group(1) if filename_extract_label and filename_extract_label.match(filename) else 'no-label'
    
    scorer = Scorer(score_load_filepath=load_filepath, 
                    score_save_filepath=save_filepath, 
                    label_extractor=extract_label, 
                    load_file_scores=load_file_scores, 
                    load_scores=load_scores) 

    try:
        data = DataHolder( source_dir=source_directory, 
                        source_regex=image_match_re or ".*png",
                        exclude=scorer.files_done )
    except NoFiles:
        print("No new files found")
        try:
            scorer.final_report()
        except NoScores:
            print("And no saved scores, either")
        return
    
    def get_size(aspect_ratio):
        h = display_height or int(display_width * aspect_ratio)
        w = display_width or int(display_height / aspect_ratio)
        return (f"{w}x{h}", w, h)
        
    app = customtkinter.CTk()
    app.title("Scorer")
    app.geometry(get_size(data.image_aspect_ratio())[0])

    on_dones = (scorer.save, scorer.final_report, app.quit)

    def check_quit(n, *args):
        if n=='q':
            raise StopIteration()

    def basic_stats(*args):
        print(f"{data.items_left} still to look at, {scorer.number_scored} already scored.")
        if log_scores:
            scorer.report()
            
    def do_score_actions(n, filename):
        if n in score_actions:
            score_actions[n](filename)

    callbacks= (check_quit, scorer.score, do_score_actions, basic_stats)

    ImageHolder( app, data.image_iterator(), callbacks=callbacks, on_dones=on_dones, size_calc=get_size )
        
    app.mainloop()

class NoScores(Exception):
    pass

class Scorer():
    def __init__(self, score_load_filepath=None, score_save_filepath=None, label_extractor=lambda a : "no-labeller", load_file_scores=True, load_scores=True):
        self.label_extractor = label_extractor
        self.score_save_filepath = score_save_filepath
        reloaded = pyjson5.load(open(score_load_filepath)) if score_load_filepath and os.path.exists(score_load_filepath) else {}
        self._scores = reloaded.get('scores',{}) if load_scores else {}
        self._file_scores = reloaded.get('file_scores',[]) if load_file_scores else []

    @property
    def files_done(self):
        return list(a[0] for a in self._file_scores)
    
    def score(self, n, filename):
        """
        Record a score of `n` to the file `filename`.
        self._scores is a dictionary mapping label -> list of scores
        self._file_scores is a list of (filename, score) tuples
        """
        n = int(n)
        label = self.label_extractor(filename)
        if label not in self._scores:
            self._scores[label] = []
        self._scores[label].append(n)
        self._file_scores.append((filename,n))

    @property
    def number_scored(self):
        return len(self._file_scores)

    def report(self):
        print(self._scores)

    def final_report(self, sort_by="score"):
        results = {}
        all_scores = [s for l in self._scores for s in self._scores[l]]
        if len(all_scores)==0:
            raise NoScores()
        
        for label in self._scores:
            label_scores = self._scores[label]
            total_score = sum(label_scores)
            n = len(label_scores)
            results[label] = (total_score/n,n)

        labels = len(results)
        count = len(all_scores)
        mean = sum(all_scores)/count
        stdv = statistics.stdev(all_scores)

        if labels>1:
            for name, (average, number) in sorted(results.items(), key=lambda x:x[1 if sort_by=="score" else 0]):
                devs = (average - mean)/(stdv/math.sqrt(number))
                print("{:>35} {:4.2f} ({:>2}) : {:5.2f}".format(name, average, number, devs))
            print("{:>3} labels, {:>4} images, (mean of {:5.2f} images per label)".format(labels, count, count/labels))
        else:
            for score in sorted(set(all_scores)):
                print("{:1} scored by {:>3} images".format(score, all_scores.count(score)))
        print("Mean score {:5.2f} +- {:5.2f}".format(mean, stdv))

    def save(self):
        if self.score_save_filepath:
            print(json.dumps({'scores':self._scores,'file_scores':self._file_scores}, indent=2), file=open(self.score_save_filepath,'w'))

class NoFiles(Exception):
    pass

class DataHolder():
    def __init__(self, source_dir, source_regex=".*", exclude = []):
        """
        Create a DataHolder which contains all files:
        - in directory source_dir
        - with filename matching source_regex
        - the filenames of which are not included in the list exclude
        and then randomly reorders them
        """
        r = re.compile(source_regex)
        self.image_filepaths = [os.path.join(source_dir, f) for f in os.listdir(source_dir) if r.match(f) and f not in exclude]
        random.shuffle(self.image_filepaths)
        self.image_number = None
        if len(self.image_filepaths)==0:
            raise NoFiles(f"No files in {source_dir} matching {source_regex}")
        
    @property
    def items_left(self):
        return len(self.image_filepaths) - self.image_number
    
    def image_iterator(self):
        """
        Return an iterator that produces the full filepath of the images
        """
        for self.image_number in range(len(self.image_filepaths)):
            yield self.image_filepaths[self.image_number]
    
    def image_aspect_ratio(self) -> float:
        """
        Return the aspect ratio (h/w) of the next image
        """
        img = Image.open(self.image_filepaths[self.image_number or 0])
        return img.height / img.width

class ImageHolder():
    def __init__(self, app:customtkinter.CTk, data_holder:iter, callbacks=(), on_dones=(), size_calc=None):
        """
        Create an ImageHolder to display images as part of a CTk app, and respond to keypresses.
        app - the app of which this is part
        data_holder - the generator of filenames
        size - a tuple (w,h)
        callbacks - a tuple of methods to be called in order for any keypress, with signature (key:string, filename:string)
        on_dones - a tuple of methods to be called in order when there are no more images to show, or when a callback raises StopIteration(), signature ()

        Any callback can rise StopIteration() to terminate the program - no further callbacks are processed, the on_dones are 
        """
        self.app = app
        self.size_calc = size_calc
        self.data_holder = data_holder
        self.callbacks = callbacks
        self.on_dones = on_dones
        self.image_label = customtkinter.CTkLabel(app, text="")
        self.image_label.grid()
        self.next_image()
        app.bind("<KeyRelease>", self.keyup)

    def next_image(self):
        self.img_filepath = self.data_holder.__next__()
        img = Image.open(self.img_filepath)
        sizes = self.size_calc(img.height/img.width)
        self.app.geometry(sizes[0])
        self.img = customtkinter.CTkImage(light_image=img, size=sizes[1:])
        self.image_label.configure(image=self.img)

    def keyup(self, e):
        try:
            for method in self.callbacks:
                method(e.char, os.path.split(self.img_filepath)[1])
            self.next_image()
        except StopIteration:
            for method in self.on_dones:
                method()

if (__name__ == "__main__"):
	main()