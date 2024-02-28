import argparse, os, shutil

from modules.scoring import ImageDatabase, ImageRecord

class CommentArgumentParser(argparse.ArgumentParser):
    def convert_arg_line_to_args(self, arg_line):
        if arg_line.startswith('#'): return [] 
        line = "=".join(a.strip() for a in arg_line.split('='))
        return [line,] if len(line) else []

def parse_arguments():
    parser = CommentArgumentParser("", fromfile_prefix_chars='@')
    parser.add_argument('-d', '--directory', help="Top level directory", required=True)
    parser.add_argument('--save_in', help="Directory to save in", required=True)
    parser.add_argument('-s', '--scores', default="scores.csv", help="Filename of scores file (relative to top level directory) from which scores are loaded")
    parser.add_argument('--threshold', default=0.0, type=float, help="Keep images scoring above threshold")
    parser.add_argument('--savefile', default=None, help="Save a scorefile for the kept images")

    return parser.parse_args()

def get_name(root, rel, i):
    return os.path.join(root, os.path.splitext(rel)[0]+f"_{i}"+os.path.splitext(rel)[1]) if i else os.path.join(root, rel)

def main():
    Args = parse_arguments()
    db = ImageDatabase(base_directory=Args.directory, loadfrom=Args.scores, trust_extensions=[".png",".jpg"])
    db.remove(test=lambda a:a.score<Args.threshold)
    if not os.path.exists(Args.save_in): os.makedirs(Args.save_in)
    for record in db.records:
        print(f"{os.path.join(Args.save_in, record.relative_path)}")
        i = 0
        while os.path.exists(get_name(Args.save_in, record.relative_path, i)): i = i + 1
        shutil.copy(os.path.join(Args.directory, record.relative_path), get_name(Args.save_in, record.relative_path, i))
    if Args.savefile:
        db.save_csv(os.path.join(Args.save_in, Args.savefile))

if __name__=='__main__':
    main()
