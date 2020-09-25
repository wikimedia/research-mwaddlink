import urllib
import urllib.parse as up

######################
## parsing titles
def normalise_title(title):
    """ 
    Normalising title (links)
    - deal with quotes
    - strip()
    - '_'--> ' '
    - capitalize first letter
    """
    title = up.unquote(title)
    title = title.strip()
    if len(title) > 0:
        title = title[0].upper() + title[1:]
    n_title = title.replace("_", " ")
    if '#' in n_title:
        n_title = n_title.split('#')[0]
    return n_title

def normalise_anchor(anchor):
    '''
    Normalising anchor  (text):
    - strip()
    - lowercase
    Note that we do not do the other normalisations since we want to match the strings from the text
    '''
    # anchor = up.unquote(anchor)
    n_anchor = anchor.strip()#.replace("_", " ")
    return n_anchor.lower()


def wtpGetLinkAnchor(wikilink):
    '''
    extract anchor and link from a wikilink from wikitextparser.
    normalise title and anchor
    '''
    ## normalise the article title (quote, first letter capital) 
    link_tmp = wikilink.title
    link = normalise_title(link_tmp)
    ## normalise the anchor text (strip and lowercase) 
    anchor_tmp = wikilink.text if wikilink.text else link_tmp
    anchor = normalise_anchor(anchor_tmp)
    return link, anchor

