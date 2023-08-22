import customtkinter
import pyjson5, os, re, random
from PIL import Image

def main():
    with open("local_settings.json") as f:
        options:dict = pyjson5.load(f)
    
    filename_extract = re.compile(options['filename_extract']) if 'filename_extract' in options else None
    scorer = Scorer(saved_scores=options.get('save_scores',None), filename_extract=filename_extract) 

    data = DataHolder( source_dir=options.get('eval_directory','.'), 
                       source_regex=options.get('match_re',".*png" ),
                       exclude=scorer.files_done )
    
    aspect_ratio = data.first_image_aspect_ratio()
    h = options.get('display_height', None) or int(options['display_width'] * aspect_ratio)
    w = options.get('display_width', None) or int(options['display_height'] / aspect_ratio)
        
    app = customtkinter.CTk()
    app.title("Scorer")
    app.geometry(f"{w}x{h}")

    def check_quit(n, *args):
        if n=='q':
            scorer.save()
            app.quit()

    ImageHolder( app, data, (w,h), callbacks=(check_quit, scorer.score, scorer.report),
                 on_dones=(scorer.save, app.quit) )
        
    app.mainloop()

class Scorer():
    def __init__(self, saved_scores=None, filename_extract=False):
        self.filename_extract = filename_extract
        self.saved_scores = saved_scores
        if self.saved_scores and os.path.exists(self.saved_scores):
            with open(self.saved_scores) as f:
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

    def report(self, n, filename):
        print(f"{len(self.files_done)} processed")

    def save(self):
        if self.saved_scores:
            print(pyjson5.dumps({'scores':self.scores,'files_done':self.files_done}), file=open(self.saved_scores,'w'))

class FilepathProvider():
    def next_image_filepath(self) -> str:
        raise NotImplemented()
    
class DataHolder(FilepathProvider):
    def __init__(self, source_dir, source_regex=".*", exclude = []):
        """
        Create a DataHolder which contains all files:
        - in directory source_dir
        - with name matching source_regex
        - the filenames of which are not included in the list exclude
        and then randomly reorder them
        """
        r = re.compile(source_regex)
        self.image_filepaths = [os.path.join(source_dir, f) for f in os.listdir(source_dir) if r.match(f) and f not in exclude]
        random.shuffle(self.image_filepaths)
        self.image_number = -1

    def next_image_filepath(self) -> str:
        """
        Return the full filepath of the next image
        """
        self.image_number += 1
        if self.image_number >= len(self.image_filepaths):
            raise StopIteration()
        return self.image_filepaths[self.image_number]
    
    def first_image_aspect_ratio(self) -> float:
        """
        Return the aspect ratio (h/w) of the next image
        """
        img = Image.open(self.image_filepaths[self.image_number+1])
        return img.height / img.width

class ImageHolder():
    def __init__(self, app:customtkinter.CTk, data_holder:FilepathProvider, size, callbacks=(), on_dones=()):
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
        self.img_filepath = self.data_holder.next_image_filepath()
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