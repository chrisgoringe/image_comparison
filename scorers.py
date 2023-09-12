import json, os, statistics

class NoScores(Exception):
    pass

class NoFiles(Exception):
    pass

class BaseScorer():
    def __init__(self, score_load_filepath=None, score_save_filepath=None, label_extractor=lambda a : "no-labeller", load_file_scores=True, load_scores=True):
        self.label_extractor = label_extractor
        self.score_save_filepath = score_save_filepath
        reloaded = json.load(open(score_load_filepath)) if score_load_filepath and os.path.exists(score_load_filepath) else {}
        self._scores = reloaded.get('scores',{}) if load_scores else {}
        self._file_scores = reloaded.get('file_scores',[]) if load_file_scores else []

    @property
    def files_done(self):
        return list(a[0] for a in self._file_scores)
    
    def score(self, n, filename):
        self._scores[n] = self._scores.get(n,0)+1

    @property
    def number_scored(self):
        return len(self._file_scores)
    
    def report(self):
        print(self._scores)

    def final_report(self, sort_by="score"):
        self.report()
    
    def save(self):
        if self.score_save_filepath:
            print(json.dumps({'scores':self._scores,'file_scores':self._file_scores}, indent=2), file=open(self.score_save_filepath,'w'))

def Scorer(type, **kwargs):
    if type=="Label":
        return LabelScorer(**kwargs)
    elif type=="AB":
        return ABScorer(**kwargs)
    return BaseScorer(**kwargs)

class LabelScorer(BaseScorer):
    def score(self, n, filename):
        n = int(n)
        label = self.label_extractor(filename)[0]
        if label not in self._scores:
            self._scores[label] = []
        self._scores[label].append(n)
        self._file_scores.append((filename,n))

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

        for name, (average, number) in sorted(results.items(), key=lambda x:x[1 if sort_by=="score" else 0]):
            print("{:>35} {:4.2f} ({:>2})".format(name, average, number))
        print("{:>3} labels, {:>4} images, (mean of {:5.2f} images per label)".format(labels, count, count/labels))

        print("Mean score {:5.2f} +- {:5.2f}".format(mean, stdv))

class ABScorer(BaseScorer):
    def score(self, n, filename):
        a,b = self.label_extractor(filename)
        self._scores[a] = self._scores.get(a,[0,0])
        self._scores[b] = self._scores.get(b,[0,0])
        if (n=='1'):
            self._scores[a][0] += 1
            self._scores[b][1] += 1
        elif (n=='2'):
            self._scores[a][1] += 1
            self._scores[b][0] += 1            

    def final_report(self, sort_by="score"):
        for label in self._scores:
            score = self._scores[label]
            percent = 100*(score[0]/(score[0]+score[1]))
            print("{:>5} wins {:>2} losses {:>2} ({:>5.1f}%)".format(label, *score, percent))