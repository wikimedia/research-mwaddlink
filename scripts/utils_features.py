import numpy as np

##########################
## getting feature-dataset
##########################
from scipy.stats import kurtosis
from Levenshtein import distance as levenshtein_distance
from Levenshtein import jaro as levenshtein_score

def getDistEmb(ent_a, ent_b, embd):
    dst = 0
    try:
        a = embd[ent_a]
        b = embd[ent_b]
        dst = (np.dot(a, b) / np.linalg.norm(a) / np.linalg.norm(b))
    except:
        pass
    if np.isnan(dst):
        dst=0
    return dst

# Return the features for each link candidate in the context of the text and the page
def get_feature_set(page, text, link, anchors, word2vec, nav2vec):
    ngram = len(text.split()) # simple space based tokenizer to compute n-grams
    freq = anchors[text][link] # How many times was the link use with this text 
    ambig = len(anchors[text]) # home many different links where used with this text
    kur = kurtosis(sorted(list(anchors[text].values()), reverse = True) + [1] * (1000 - ambig)) # Skew of usage text/link distribution
    w2v = getDistEmb(page, link,word2vec) # W2V Distance between the source and target page
    nav = getDistEmb(page, link, nav2vec) # Nav Distance between the source and target page
    leven = levenshtein_score(text.lower(),link.lower())
    return (ngram, freq, ambig, kur, w2v, nav, leven)