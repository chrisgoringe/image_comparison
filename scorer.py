import customtkinter
import pyjson5, os, re, random
from PIL import Image

def main():
    with open("local_settings.json") as f:
        options:dict = pyjson5.load(f)
    
    filename_extract = re.compile(options['filename_extract']) if 'filename_extract' in options else None
    score_save_filepath = options.get('score_save_filepath',None) or os.path.join(options.get('eval_directory','.'), 
                                                                                  options.get('score_save_filename', 'scores.json'))
    
    scorer = Scorer(score_save_filepath=score_save_filepath, filename_extract=filename_extract) 

    if 'drop_done_list' in options and options['drop_done_list']:
        scorer.files_done = []

    data = DataHolder( source_dir=options.get('eval_directory','.'), 
                       source_regex=options.get('match_re',None) or ".*png",
                       exclude=scorer.files_done )
    
    aspect_ratio = data.image_aspect_ratio()
    h = options.get('display_height', None) or int(options['display_width'] * aspect_ratio)
    w = options.get('display_width', None) or int(options['display_height'] / aspect_ratio)
        
    app = customtkinter.CTk()
    app.title("Scorer")
    app.geometry(f"{w}x{h}")

    on_dones = (scorer.save, scorer.final_report, app.quit)
    def check_quit(n, *args):
        if n=='q':
            for method in on_dones:
                method()
    def basic_stats(*args):
        print(f"{data.items_left} still to look at, {scorer.number_scored} already scored.")
    def maybe_move(n, filename):
        if 'good_directory' in options and (n=='4' or n=='5'):
            target = os.path.join(options['good_directory'], filename)
            while os.path.exists(target):
                target = os.path.splitext(target)[0]+'x'+os.path.splitext(target)[1]
            os.rename(os.path.join(options.get('eval_directory','.'),filename), target)

    callbacks= (check_quit, scorer.score, maybe_move, basic_stats)

    ImageHolder( app, data.image_iterator(), (w,h), callbacks=callbacks, on_dones=on_dones )
        
    app.mainloop()

class Scorer():
    def __init__(self, score_save_filepath=None, filename_extract=False):
        self.filename_extract = filename_extract
        self.score_save_filepath = score_save_filepath
        if self.score_save_filepath and os.path.exists(self.score_save_filepath):
            with open(self.score_save_filepath) as f:
                reloaded = pyjson5.load(f)
                self.scores = reloaded['scores']
                self.files_done = reloaded['files_done']
        else:
            self.scores = {}
            self.files_done = []

    def score(self, n, filename):
        if self.filename_extract:
            m = self.filename_extract.match(filename)
            bucket = m.group(1) if m else "none"
        else:
            bucket = "none"
        if bucket not in self.scores:
            self.scores[bucket] = {}
        self.scores[bucket][n] = self.scores[bucket].get(n,0) + 1
        self.files_done.append(filename)

    @property
    def number_scored(self):
        return len(self.files_done)

    def final_report(self, *args):
        results = {}
        for style in self.scores:
            total_score = 0
            n = 0
            for score in self.scores[style]:
                n += self.scores[style][score]
                total_score += self.scores[style][score] * int(score)

            results[style] = (total_score/n,n)

        for name, (average, number) in sorted(results.items(), key=lambda x:x[1]):
            print("{:>35} {:4.2f} ({:>2}) ".format(name, average, number))

    def save(self):
        if self.score_save_filepath:
            print(pyjson5.dumps({'scores':self.scores,'files_done':self.files_done}), file=open(self.score_save_filepath,'w'))

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
        img = Image.open(self.image_filepaths[0])
        return img.height / img.width

class ImageHolder():
    def __init__(self, app:customtkinter.CTk, data_holder:iter, size, callbacks=(), on_dones=()):
        """
        Create an ImageHolder to display images as part of a CTk app, and respond to keypresses.
        app - the app of which this is part
        data_holder - the generator of filenames
        size - a tuple (w,h)
        callbacks - a tuple of methods to be called in order for any keypress, with signature (key:string, filename:string)
        on_dones - a tuple of methods to be called in order when there are no more images to show, signature ()
        """
        self.data_holder = data_holder
        self.size = size
        self.callbacks = callbacks
        self.on_dones = on_dones
        self.image_label = customtkinter.CTkLabel(app, text="")
        self.image_label.grid()
        self.next_image()
        app.bind("<KeyRelease>", self.keyup)
       
    def next_image(self):
        self.img_filepath = self.data_holder.__next__()
        self.img = customtkinter.CTkImage(light_image=Image.open(self.img_filepath), size=self.size)
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