import pyjson5
import os

def report(scores):
    results = {}
    for style in scores:
        total_score = 0
        n = 0
        fives = 0
        for score in scores[style]:
            n += scores[style][score]
            total_score += scores[style][score] * int(score)
            fives += score=='5'

        results[style] = (total_score/n,n,fives)

    for name, (average, number, fives) in sorted(results.items(), key=lambda x:x[1]):
        print("{:>35} {:4.2f} ({:>2}) ({:>2}) ".format(name, average, number, fives))

def main():
    with open("local_settings.json") as f:
        options:dict = pyjson5.load(f)

    score_save_filepath = options.get('score_save_filepath',None) or os.path.join(options.get('eval_directory','.'), 
                                                                                  options.get('score_save_filename', 'scores.json'))
    with open(score_save_filepath) as f:
        scores:dict = pyjson5.load(f)

    report(scores['scores'])

if __name__ == "__main__":
    main()