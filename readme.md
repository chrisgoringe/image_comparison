# AB scorer

From a set of images, creates an `image_scores.json` file suitable for training a model (or other use).

Edit the top of the `image_ab_scorer.py` file - the only things you need to change are:
- `top_level_image_directory` should point to a directory holding the images (subdirectories are included)
- `load_from` which should be `""` for your first run, and then the same as `score_filename` thereafter. 
That way the scores will be loaded from and saved to the same file, but that's ok, because a numbered backup is also saved each time
under the name `[savename]_xxxx.json`

```python
# The directory where the images are (subfolders are included)
    top_level_image_directory = r""
# ...stuff to leave for now...

# Scores file (in the top_level_image_directory) to load from. Set to "" or None to start without any scores.
    load_from = "scores.json"
# Name under which to save the scores at the end. An additional file, `same_name_x.json` (where x is number of comparisons to date) is also saved.
    score_filename = "scores.json"
# Save a csv file as well?
    csv_filename = None
```

Then run. Click 1 to prefer the left image, 2 to prefer the right image, or q to quit.

Then edit the file to set `load_from` to the same as `score_filename` and run a few more times.

## Comparing and converging

After a few runs you'll have a set of files like
```
scores_200.json
scores_400.json
...
scores_1000.json
```
(note that 100 AB comparisons counts as 200, because we keep track of comparisons per image)

If you take a look at `compare_scorefiles.py` and edit 
```python
    top_level_image_directory = r"C:\Users\chris\Documents\GitHub\ComfyUI_windows_portable\ComfyUI\output\training4"
    score_filename = "scores.json"
```
appropriately then run it, you should get a graph like this (this example is for an example which has had lots of runs!):

![scorefile](media/scorefile_convergence.png)

The x axis is the number of comparisons, and the y axis is the spearman rank correlation between the scores before and after the run. Spearman rank correlation is a measure of how well correlated the _ordering_ of a set of values is. So the images are lined up in order from highest scoring to lowest scoring, before and after the set of AB comparisons, and the ranking is compared. A value of 1 corresponds to the same order, 0 to uncorrelated, and -1 to reversed order.

As you train the database through your AB comparison, you expect the ranking to become gradually more stable as the images get 'sorted out'. If the ranking is changing less during a run, the spearman value will get closer to 1. So you are looking for it to plateau (roughly), as can be seen from around 4000-6000 in this example.

---

# More technical stuff

## File format

The scores file is a json file holding a single python dictionary. The dictionary is of the form:

```python
{
    "ImageRecords": {
        "[imagepath relative to top level directory]": {
            "relative_filepath": "[imagepath relative to top level directory]",  # yes, repeated
            "score": 1.3069393352445966, # the score
            "comparisons": 3 # the number of times this image has been compared
        },
        #...for all images...
    },
    "Metadata": {}
}
```

## Scoring 

The scores are updated using [Elo ratings](https://en.wikipedia.org/wiki/Elo_rating_system) with `k = 0.7`:
```python
        delta = winner.score - loser.score
        p = 1.0/(1.0+math.pow(10,-delta))
        winner.score += (1-p) * k_fac * self.k
        loser.score -= (1-p) * k_fac * self.k
```
`k = 0.7` and `k_fac = 1.0` by default. In the arguments you'll find this:
```python
    k = 0.7
    weight_k_by_speed = False
    default_seconds = 1.2
    weighting_limits = (0.5, 2.0)
```
If you set `weight_k_by_speed` to true, then the speed with which you make your decision will be taken into account - 
quick decisions will be weighted more than slow ones (you had to think, so maybe it's close...). The weighting is
given by `k_fac = Args.default_seconds / time_taken`, with `k_fac` clamped within `weighting_limits = (min, max)`.
Default seconds should be your typical decision time (given at the end of each run)

## AB Comparison theory

In theory, a set of N images can be fully ordered in approximately `X=ln(2).N.(ln(N)-1)` comparisons.


, so comparisons per image is `X/N = ln(2).(ln(N)-1)`.

|N|X|X/N|
|-|-|-|
|100|250|2.5|
|1000|4100|4.1|
|10000|57000|5.7|
|100000|730000|7.3|

In practice, with human consistency 75-85% (depending on variation in the dataset) this number might be multiplied by 1.5 - 2.0 (allowing each 'wrong' response to be cancelled by an additional right response).

One way of thinking is that each image should be compared `1.5-2 x X/N` times. The stats output at the end of a run will help!