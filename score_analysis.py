from scorer import Scorer
from options import save_filepath

if __name__ == "__main__":
    s = Scorer(save_filepath)
    s.final_report()
    s.final_report(sort_by="alpha")