import sys, os
import pickle
import glob
import numpy as np

if len(sys.argv) >= 2:
    wiki_id = sys.argv[1]
else:
    wiki_id = "enwiki"
## filter the anchor dictionary based on wikidata-properties
## filter all links that are an instance-of the following wikidata-items
list_qid_filter = [
    # non-content pages
    "Q4167410",  # disambiguation-pages
    "Q13406463",  # list-pages
    # dates
    "Q3186692",  # calendar year-pages
    "Q577",  # year
    "Q573",  # day
    "Q39911",  # decade
    "Q578",  # century
    "Q36507",  # millenium
    "Q47150325",  # calendar day of a given year
    "Q47018478",  # calendar month of a given year
    "Q205892",  # calendar date
    "Q14795564",  # Point in time with respect to recurrent timeframe
    "Q18340514",  # events in a specific year or time period
    # units
    "Q1978718",  # unit of length
    "Q1790144",  # unit of time
    "Q1302471",  # unit of volume
    "Q3647172",  # unit of mass
    "Q2916980",  # unit of energy
    "Q3550873",  # unit of information
    "Q8142",  # currency
    "Q27084",  # parts-per-notation
    # names
    "Q202444",  # given name
    "Q1243157",  # double name
    "Q3409032",  # unisex given name
    "Q12308941",  # male given name
    "Q11879590",  # female given name
]
per_wiki_qid_filter = {
    "enwiki": [
        "Q6256",  # country names (T386867)
    ]
}

for special_wiki, extra_filters in per_wiki_qid_filter.items():
    if wiki_id == special_wiki:
        list_qid_filter = list_qid_filter + extra_filters
        break

anchors = pickle.load(open("../../data/{0}/{0}.anchors.pkl".format(wiki_id), "rb"))
pageids = pickle.load(open("../../data/{0}/{0}.pageids.pkl".format(wiki_id), "rb"))
wdproperties = pickle.load(
    open("../../data/{0}/{0}.wdproperties.pkl".format(wiki_id), "rb")
)

anchors_filtered = {}
# iterate through all anchors
for a, dict_a in anchors.items():
    dict_a_new = {}
    # iterate through all links of an anchor
    for l_title, l_n in dict_a.items():
        l_title_remove = False
        # get the link's pageid
        l_pid = pageids.get(l_title)
        # get all items for which this is an instance-if
        l_wdp_list = wdproperties.get(l_pid, [])
        # if any of the instance-of items match the filter, remove the link
        for l_wdp in l_wdp_list:
            if l_wdp in list_qid_filter:
                l_title_remove = True
                break

        if l_title_remove == False:
            dict_a_new[l_title] = l_n
    # if the anchor has no more links, we remove
    if len(dict_a_new) > 0:
        anchors_filtered[a] = dict_a_new


## dump as pickle
output_path = "../../data/{0}/{0}.anchors".format(wiki_id)
with open(output_path + ".pkl", "wb") as handle:
    pickle.dump(anchors_filtered, handle, protocol=4)
