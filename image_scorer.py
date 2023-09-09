import customtkinter
import os, re, random
from PIL import Image
from options import *
from scorers import Scorer, NoFiles, NoScores

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
        return filename_extract_label.match(filename).groups() if filename_extract_label and filename_extract_label.match(filename) else paired_image_sub
    
    scorer = Scorer(type=scorer_type,
                    score_load_filepath=load_filepath, 
                    score_save_filepath=save_filepath, 
                    label_extractor=extract_label, 
                    load_file_scores=load_file_scores, 
                    load_scores=load_scores) 

    try:
        data = DataHolder( source_dir=source_directory, 
                        source_regex=image_match_re or ".*png",
                        paired_image_sub=paired_image_sub,
                        exclude=scorer.files_done )
    except NoFiles:
        print("No new files found")
        try:
            scorer.final_report()
        except NoScores:
            print("And no saved scores, either")
        return
    
    def get_size(aspect_ratio, n=1):
        h = display_height or int(display_width * aspect_ratio)
        w = display_width or int(display_height / aspect_ratio)
        return (f"{n*w}x{h}", w, h)
        
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

class DataHolder():
    def __init__(self, source_dir, source_regex=".*", paired_image_sub=None, exclude = []):
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
        if paired_image_sub:
            self.paired_image_sub = lambda a : (a, re.sub(paired_image_sub[0], paired_image_sub[1], a))
        else:
            self.paired_image_sub = lambda a : (a, None)
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
            yield self.paired_image_sub(self.image_filepaths[self.image_number])
    
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
        self.image_label.grid(row=0, column=0)
        self.image_label2 = customtkinter.CTkLabel(app, text="")
        self.image_label2.grid(row=0, column=1)
        self.next_image()
        app.bind("<KeyRelease>", self.keyup)

    def next_image(self):
        self.img_filepath, self.img_filepath2 = self.data_holder.__next__()

        img = Image.open(self.img_filepath)
        sizes = self.size_calc(img.height/img.width, (2 if self.img_filepath2 else 1))
        self.app.geometry(sizes[0])
        self.img = customtkinter.CTkImage(light_image=img, size=sizes[1:])
        self.image_label.configure(image=self.img)
        if self.img_filepath2:
            img2 = Image.open(self.img_filepath2)
            self.img2 = customtkinter.CTkImage(light_image=img2, size=sizes[1:])
            self.image_label2.configure(image=self.img2)

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