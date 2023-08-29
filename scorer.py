import customtkinter
import pyjson5, os, re, random, json, math, statistics
from PIL import Image
from options import *

def main():
    if good_directory and not os.path.exists(good_directory):
        os.makedirs(good_directory)
   
    def extract_label(filename):
        return filename_extract.match(filename).group(1) if filename_extract and filename_extract.match(filename) else None
    
    scorer = Scorer(score_save_filepath=save_filepath, label_extractor=extract_label, load_done_list=load_done_list, load_scores=load_scores) 

    data = DataHolder( source_dir=source_directory, 
                       source_regex=image_match_re or ".*png",
                       exclude=scorer.files_done )
    
    def get_size(aspect_ratio):
        h = display_height or int(display_width * aspect_ratio)
        w = display_width or int(display_height / aspect_ratio)
        return (f"{w}x{h}", w, h)
        
    app = customtkinter.CTk()
    app.title("Scorer")
    app.geometry(get_size(data.image_aspect_ratio())[0])

    on_dones = (scorer.save, scorer.final_report, app.quit) if save_scores else (scorer.final_report, app.quit)

    def check_quit(n, *args):
        if n=='q':
            for method in on_dones:
                method()
            raise Exception("Quit")

    def basic_stats(*args):
        print(f"{data.items_left} still to look at, {scorer.number_scored} already scored.")
        if log_scores:
            scorer.report()
            
    def maybe_move_or_delete(n, filename):
        if good_directory and n in good_match:
            target = os.path.join(good_directory, filename)
            x = 1
            while os.path.exists(target):
                target = os.path.splitext(target)[0]+f"-{x}"+os.path.splitext(target)[1]
                x += 1
            os.rename(os.path.join(source_directory, filename), target)
        elif n in delete_match:
            os.remove(os.path.join(source_directory,filename))

    callbacks= (check_quit, scorer.score, maybe_move_or_delete, basic_stats)

    ImageHolder( app, data.image_iterator(), callbacks=callbacks, on_dones=on_dones, size_calc=get_size )
        
    app.mainloop()

class Scorer():
    def __init__(self, score_save_filepath=None, label_extractor=None, load_done_list=True, load_scores=True):
        self.label_extractor = label_extractor
        self.score_save_filepath = score_save_filepath
        reloaded = pyjson5.load(open(self.score_save_filepath)) if self.score_save_filepath and os.path.exists(self.score_save_filepath) else {}
        self.scores = reloaded['scores'] if 'scores' in reloaded and load_scores else {}
        self.files_done = reloaded['files_done'] if 'files_done' in reloaded and load_done_list else []

    def score(self, n, filename):
        """
        Give a score of `n` to the file `filename`
        """
        label = self.label_extractor(filename) or "no-label" if self.label_extractor else "no-labeller"
        if label not in self.scores:
            self.scores[label] = {}
        self.scores[label][n] = self.scores[label].get(n,0) + 1
        self.files_done.append(filename)

    @property
    def number_scored(self):
        return len(self.files_done)

    def report(self):
        print(self.scores)

    def final_report(self, sort_by="score"):
        results = {}
        all_scores = []
        for label in self.scores:
            total_score = 0
            n = 0
            for score in self.scores[label]:
                n += self.scores[label][score]
                total_score += self.scores[label][score] * int(score)
                all_scores.extend([int(score)]*self.scores[label][score])
            results[label] = (total_score/n,n)

        labels = len(results)
        count = len(all_scores)
        if (count==0):
            print("No scores found")
            return
        mean = sum(all_scores)/count
        stdv = statistics.stdev(all_scores)

        for name, (average, number) in sorted(results.items(), key=lambda x:x[1 if sort_by=="score" else 0]):
            devs = (average - mean)/(stdv/math.sqrt(number))
            print("{:>35} {:4.2f} ({:>2}) : {:5.2f}".format(name, average, number, devs))
        
        print("{:>3} labels, {:>4} images, (mean of {:5.2f} per label)".format(labels, count, count/labels))
        print("Mean score {:5.2f} +- {:5.2f}".format(mean, stdv))


    def save(self):
        if self.score_save_filepath:
            print(json.dumps({'scores':self.scores,'files_done':self.files_done}, indent=2), file=open(self.score_save_filepath,'w'))

class DataHolder():
    def __init__(self, source_dir, source_regex=".*", exclude = []):
        """
        Create a DataHolder which contains all files:
        - in directory source_dir
        - with name matching source_regex
        - the filenames of which are not included in the list exclude
        and then randomly reorders them
        """
        r = re.compile(source_regex)
        self.image_filepaths = [os.path.join(source_dir, f) for f in os.listdir(source_dir) if r.match(f) and f not in exclude]
        random.shuffle(self.image_filepaths)
        self.image_number = None
        if len(self.image_filepaths)==0:
            raise Exception(f"No files in {source_dir} matching {source_regex}")
        
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
        Return the aspect ratio (h/w) of the first image
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
        on_dones - a tuple of methods to be called in order when there are no more images to show, signature ()
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
        for method in self.callbacks:
            method(e.char, os.path.split(self.img_filepath)[1])
        try:
            self.next_image()
        except StopIteration:
            for method in self.on_dones:
                method()

if (__name__ == "__main__"):
	main()