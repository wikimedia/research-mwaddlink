import os, sys
import datetime
import calendar
import time
import string
import random
import pickle
from pyspark.sql import SparkSession
from pyspark.sql import functions as F, types as T, Window
import urllib

# from utils_parse import normalise_title, normalise_anchor


def normalise_title(title):
    """
    Normalising title (links)
    - deal with quotes
    - strip()
    - '_'--> ' '
    - capitalize first letter
    """
    title = urllib.parse.unquote(title)
    title = title.strip()
    if len(title) > 0:
        title = title[0].upper() + title[1:]
    n_title = title.replace("_", " ")
    if "#" in n_title:
        n_title = n_title.split("#")[0]
    return n_title


def normalise_anchor(anchor):
    #     anchor = urllib.parse.unquote(anchor)
    n_anchor = anchor.strip()  # .replace("_", " ")
    return n_anchor.lower()


def extract_article(row):
    """Extract the content of the article.
    normalize the titles"""
    #     redirect = row.page_redirect_title if row.page_redirect_title is not None else ""
    return T.Row(
        pid=row.page_id,
        title=normalise_title(row.page_title),
        title_rd=normalise_title(row.page_redirect_title),
        wikitext=row.revision_text,
    )


import re

links_regex = re.compile(
    r"\[\[(?P<link>[^\n\|\]\[\<\>\{\}]{0,256})(?:\|(?P<anchor>[^\[]*?))?\]\]"
)


def get_links(page):
    links = []
    for m in links_regex.findall(page.wikitext):
        link = normalise_title(m[0])
        anchor = m[1] if len(m) > 1 and len(m[1]) > 0 else link
        if len(link) > 0:
            links.append(
                T.Row(
                    pid=page.pid,
                    title=page.title,
                    link=link,
                    anchor=normalise_anchor(anchor),
                )
            )
    return links


## number of occurrences of each anchor astext
import re

references_regex = re.compile(r"<ref[^>]*>[^<]+<\/ref>")


def get_plain_text_without_links(row):
    """ Replace the links with a dot to interrupt the sentence and get the plain text """
    wikicode = row.wikitext
    wikicode_without_links = re.sub(links_regex, ".", wikicode)
    wikicode_without_links = re.sub(references_regex, ".", wikicode_without_links)
    ## we dont have mwparserfromhell on the spark-cluster yet
    try:
        text = mwparserfromhell.parse(wikicode_without_links).strip_code()
    except:
        text = wikicode_without_links
    text = wikicode_without_links
    return T.Row(pid=row.pid, title=normalise_title(row.title), text=text.lower())


## get chunks
def get_chunks(row):
    return [
        T.Row(pid=row.pid, chunk=blocks.strip())
        for blocks in re.split('[\n\.,;:()!"]', row.text)
        if len(blocks.strip()) > 0
    ]


def get_ngrams(txt, n):
    ngrams = []
    words = txt.split()
    if len(words) >= n:
        ngram_list = [words[i : i + n] for i in range(len(words) - n + 1)]
        for e in ngram_list:
            ngrams.append(" ".join(e))
    return ngrams


def get_valid_ngrams(row):
    text = row.chunk
    found_anchors = []
    for n in range(10, 0, -1):
        ngrams = get_ngrams(text, n)
        for ng in ngrams:
            if ng in anchors_keys:
                found_anchors.append(ng)
    #                 text.replace(ng, " @ ")
    return [T.Row(pid=row.pid, anchor=a) for a in found_anchors]


## usage


if len(sys.argv) >= 2:
    lang = sys.argv[1]
else:
    lang = "en"

wiki = lang + "wiki"

snapshot = "2020-07"
## there is more lag here (on 2020-09-07 I could only find the 2020-07 snapshot)

spark = (
    SparkSession.builder.master("yarn")
    .appName("generating-anchors")
    .enableHiveSupport()
    .getOrCreate()
)

wikipedia_all = (
    ## select table
    spark.read.table("wmf.mediawiki_wikitext_current")
    ## select wiki project
    .where(F.col("wiki_db") == wiki)
    .where(F.col("snapshot") == snapshot)
    ## main namespace
    .where(F.col("page_namespace") == 0)
    ## no redirect-pages
    #     .where(F.col('page_redirect_title')=='')
    .where(F.col("revision_text").isNotNull())
    .where(F.length(F.col("revision_text")) > 0)
)

## extracting pid, title, title_rd, and the wikitext
## titles are normalized
wikipedia = spark.createDataFrame(
    wikipedia_all.rdd.map(extract_article).filter(lambda r: r is not None)
)

## only redirects
redirects = spark.createDataFrame(
    wikipedia.where(F.col("title_rd") != "").rdd.map(
        lambda r: T.Row(title_from=r.title, title_to=r.title_rd)
    )
).distinct()

## only articles (no redirect title)
articles = wikipedia.where(F.col("title_rd") == "").select("pid", "title", "wikitext")

## extract the links
links = spark.createDataFrame(articles.rdd.flatMap(get_links))

links_resolved = links.join(
    redirects, links["link"] == redirects["title_from"], how="leftouter"
).select(
    "pid",
    "title",
    "anchor",
    ## resolved link: if redirect use title_to otherwise original link
    F.coalesce(F.col("title_to"), F.col("link")).alias("link"),
)

## only keep candidates for which there is a link
links_resolved_articles = links_resolved.join(
    articles, links_resolved["link"] == articles["title"], how="leftsemi"
)

anchors_aslinks = (
    links_resolved_articles.select("anchor")
    .where("LENGTH(anchor)>0")
    .filter("anchor not rlike '^[0-9]+$' and anchor not rlike '^[0-9]+[/-][0-9]+$'")
    .groupBy("anchor")
    .agg(F.count("*").alias("aslink"))
    .where("aslink>1")  ## anchor has to appear more than once?
)

## counting ngrams
anchors_keys = set(
    anchors_aslinks.select("anchor").rdd.map(lambda r: r.anchor).collect()
)
chunks = articles.rdd.map(get_plain_text_without_links).flatMap(get_chunks)
matched_ngrams = (
    spark.createDataFrame(chunks.flatMap(get_valid_ngrams))
    .groupBy("anchor", "pid")
    .agg(F.count("*").alias("occ"))
)

anchors_astext = matched_ngrams.groupBy("anchor").agg(
    F.sum(F.col("occ")).alias("astext")
)

## join the anchors_aslink and anchors_astext to calculate the link probability
anchors_lp = (
    anchors_aslinks.join(anchors_astext, on="anchor", how="left_outer")
    .fillna(0)
    .withColumn("linkprob", F.col("aslink") / (F.col("astext") + F.col("aslink")))
)

## filter those anchors which exceed some probability
## calculate link probability
## here we will immediately calculate the link probability of each anchor-word
## - calculate the number of occurrences the anchor n-gram occurs astext n_t
## - calculate the number of occurrences the anchor n-gram occurs aslink n_l (sum all links from above)
## - p = n_t/(n_t+n_l) > pmin with pmin ~0.065
##- remove anchors with link probability below a given threshold

lp_min = 0.065  ## from Tiziano+Bob (Witten 2008)
links_resolved_articles_filtered = (
    links_resolved_articles.distinct()  ## a link can appear multiple times (we counted befiore but here keep only distinct)
    .join(anchors_lp, on="anchor", how="left")
    .where(F.col("linkprob") >= lp_min)
)

links_formatted = (
    links_resolved_articles_filtered.groupBy("anchor", "link")
    .agg(F.count(F.col("title")).alias("n"))
    .groupBy("anchor")
    .agg(F.collect_list(F.struct(F.col("link"), F.col("n"))).alias("candidates"))
)
# links_formatted.write.mode('overwrite').parquet('/user/mgerlach/en.anchors.parquet')
df_pd = links_formatted.toPandas()
df_pd["candidates"] = df_pd["candidates"].apply(lambda x: dict(x))
dict_anchors = df_pd.set_index("anchor")["candidates"].to_dict()
# store the dictionaries into the language data folder
output_path = "../../data/{0}/{0}.anchors".format(lang)
with open(output_path + ".pkl", "wb") as handle:
    pickle.dump(dict_anchors, handle, protocol=pickle.HIGHEST_PROTOCOL)


## saving articles-dict
df_articles = (articles.select("pid", "title")).toPandas()
# store the dictionaries into the language data folder
output_path = "../../data/{0}/{0}.pageids".format(lang)
with open(output_path + ".pkl", "wb") as handle:
    pickle.dump(
        df_articles.set_index("title")["pid"].to_dict(),
        handle,
        protocol=pickle.HIGHEST_PROTOCOL,
    )

## saving redirects dictionary
df_redirects = (redirects.select("title_from", "title_to")).toPandas()
# store the dictionaries into the language data folder
output_path = "../../data/{0}/{0}.redirects".format(lang)
with open(output_path + ".pkl", "wb") as handle:
    pickle.dump(
        df_redirects.set_index("title_from")["title_to"].to_dict(),
        handle,
        protocol=pickle.HIGHEST_PROTOCOL,
    )
