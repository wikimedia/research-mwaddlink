import urllib
import urllib.parse as up
def normalise_title(title):
    """ Replace _ with space, remove anchor, capitalize """
    title = up.unquote(title)
    title = title.strip()
    if len(title) > 0:
        title = title[0].upper() + title[1:]
    n_title = title.replace("_", " ")
    if '#' in n_title:
        n_title = n_title.split('#')[0]
    return n_title

def normalise_anchor(anchor):
    # anchor = up.unquote(anchor)
    n_anchor = anchor.strip()#.replace("_", " ")
    return n_anchor.lower()


