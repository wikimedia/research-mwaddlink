import os, sys
import string
import pickle
import pandas as pd
import pyarrow.parquet as pq
import json
from pyspark.sql import SparkSession
from pyspark.sql import functions as F, types as T, Window

if len(sys.argv) >= 2:
    wiki_id = sys.argv[1]
else:
    wiki_id = "enwiki"

# TODO: automatically update snapshot
snapshot = "2021-03-01"
# list of propoerties for which to extract the qid-values
# P31=instance-of
# TODO: make this custopmizable
list_properties_keep = ["P31"]

spark = (
    SparkSession.builder.master("yarn")
    .appName("generating-wdproperties")
    .enableHiveSupport()
    .getOrCreate()
)

## all wikidata items with wikipedia-article in a given project (main namespace)
df_wd = (
    spark.read.table("wmf.wikidata_item_page_link")
    ## snapshot: this is a partition!
    .where(F.col("snapshot") == snapshot)
    .where(F.col("wiki_db") == wiki_id)
    .where(F.col("page_namespace") == 0)
    .select(
        F.col("item_id"),
        F.col("page_id"),
    )
)

## wikidata-dump
df_ent_claims = (
    spark.read.table("wmf.wikidata_entity")
    ## snapshot: this is a partition!
    .where(F.col("snapshot") == snapshot)
    .withColumnRenamed("id", "item_id")
    .join(df_wd, on="item_id", how="inner")
    .select("item_id", "claims", "page_id")
    .where(F.col("claims").isNotNull())
    .withColumn("claims_exploded", F.explode(F.col("claims")))
    .select("item_id", "claims_exploded", "page_id")
    .withColumnRenamed("claims_exploded", "claim")
)

# extract the statement-values and the statement-properties of the claims
@F.udf(returnType=T.StringType())
def get_value_from_statement_dict(x):
    """
    if the statement-value is a wikibase-item,
    the statement-value is a dict (in the form of a string).
    the stament-value (the wikidata-item) is under the key "id"
    """
    try:
        val_x = json.loads(x).get("id")
    except:
        val_x = None
    return val_x


df_statements = (
    df_ent_claims
    ## only keep statements involving specific properties
    .withColumn("statement_property", F.col("claim.mainSnak.property"))
    ## only keep statements with wikidata-id as a value
    .withColumn("statement_value_type", F.col("claim.mainSnak.dataType"))
    ## get the dictionary with the statement-value
    .withColumn("statement_value_dict", F.col("claim.mainSnak.dataValue.value"))
    ## extract the qid of the statement-value
    .withColumn(
        "statement_value",
        F.when(
            (F.col("statement_property").isin(list_properties_keep))
            & (F.col("statement_value_type") == "wikibase-item"),
            get_value_from_statement_dict(F.col("statement_value_dict")),
        ).otherwise(None),
    )
    .where(F.col("statement_value").isNotNull())
    .select("page_id", "item_id", "statement_property", "statement_value")
)

## aggregate all statement-values (qids) for a given page-id
df_wdproperties = df_statements.groupby("page_id").agg(
    F.collect_set(F.col("statement_value")).alias("statement_value_qid")
)

## save a dict  as pkl {pageid: [list of qids]}
PATH_local = "../../data/%s/" % wiki_id
PATH_hadoop = "/tmp/%s/mwaddlink/" % (os.environ["USER"])  # "/tmp/$USER/mwaddlink

FILE_hadoop = PATH_hadoop + "%s.wdproperties.parquet" % wiki_id
FILE_local = PATH_local + "%s.wdproperties.parquet" % wiki_id

df_wdproperties.write.mode("overwrite").parquet(FILE_hadoop)

if os.path.isdir(FILE_local):
    os.system("rm -rf %s" % FILE_local)
os.system("hadoop fs -get %s %s" % (FILE_hadoop, FILE_local))
dataset = pq.ParquetDataset(FILE_local)
table = dataset.read()
pd_wdproperties = table.to_pandas()
output_path = PATH_local + "{0}.wdproperties".format(wiki_id)
with open(output_path + ".pkl", "wb") as handle:
    pickle.dump(
        pd_wdproperties.set_index("page_id")["statement_value_qid"].to_dict(),
        handle,
        protocol=pickle.HIGHEST_PROTOCOL,
    )

os.system("rm -rf %s" % (FILE_local))
os.system("hdfs dfs -rm -r %s" % (FILE_hadoop))
