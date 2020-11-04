import os, sys
import datetime
import calendar
import time
import string
import random
import argparse
from pyspark.sql import functions as F, types as T, Window, SparkSession


'''
process webrequest table to get reading sessions
- returns filename where reading sessions are stored locally
    - ../data/<LANG>/<LANG>.reading-sessions

- USAGE:
PYSPARK_PYTHON=python3.7 PYSPARK_DRIVER_PYTHON=python3.7 spark2-submit --master yarn --executor-memory 8G --executor-cores 4 --driver-memory 2G  generate_features_nav2vec-01-get-sessions.py -l simple

- optional
    - t1, start-date (incusive)
    - t2, end-date (exclusive)

'''

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lang","-l",
                        default="enwiki",
                        type = str,
                        help="language to parse (en or enwiki)")

    parser.add_argument("--start","-t1",
                        default=None,
                        type = str,
                        help="start day to parse [inclusive] (YYYY-MM-DD); default: previous day - 7days")

    parser.add_argument("--end","-t2",
                        default=None,
                        type = str,
                        help="end day to parse [exclusive] (YYYY-MM-DD); default: current day")

    args = parser.parse_args()
    lang = args.lang.replace('wiki','')
    wiki_db = lang+'wiki'


    t1 = args.start
    t2 = args.end
    if t1!=None and t2!=None:
        try:
            date_start = datetime.datetime.strptime(t1,'%Y-%m-%d')
            date_end = datetime.datetime.strptime(t2,'%Y-%m-%d')
        except ValueError:
            print('Provide correct day-format YYYY-MM-DD')
    else:

        date_start = datetime.date.today()-datetime.timedelta(days=8)
        date_end = datetime.date.today()


    date_start_str = date_start.strftime('%Y-%m-%d')
    date_end_str = date_end.strftime('%Y-%m-%d')


    #### other parameters
    ## filter pageviews from actor with more than 500 pageviews
    ## the aim is to filter automated traffic that is not tagged as spider
    n_p_max = 500 ## maximum number of pageviews/user/day
    n_p_min = 1 ## minimum number of pageviews/user/day

    ## filtering sessions
    dt = 3600 ## cutoff for splitting sessions(interevent time between 2 pageivews)
    nlen_min = 2 ## min length of session
    nlen_max = 30 ## max length of session

    ## sessions will be saved locally in filename_save
    path_save = os.path.abspath('../../data/%s/'%lang)
    # filename_save = '%s.reading-sessions-%s--%s'%(lang,date_start_str,date_end_str)
    filename_save = '%s.reading-sessions'%(lang)

    ## tmp-directory for data on hive (will be deleted)
    base_dir_hdfs = '/tmp/mwaddlink/sessions'

    ### start
    spark = SparkSession.builder\
        .master('yarn')\
        .appName('reading-sessions')\
        .enableHiveSupport()\
        .getOrCreate()

    ########
    ## query
    ################################################
    ## time-window
    ts_start = calendar.timegm(date_start.timetuple())
    ts_end = calendar.timegm(date_end.timetuple())
    row_timestamp = F.unix_timestamp(F.concat(
        F.col('year'), F.lit('-'), F.col('month'), F.lit('-'), F.col('day'),
        F.lit(' '), F.col('hour'), F.lit(':00:00')))

    ## window for counting pageviews per actor per day
    w_p = Window.partitionBy(F.col('actor_signature_per_project_family'), F.col('year'), F.col('month'), F.col('day'))



    ### actor table (filtered webrequests)
    ## https://wikitech.wikimedia.org/wiki/Analytics/Data_Lake/Traffic/Pageview_actor
    df_actor = (
        spark.read.table('wmf.pageview_actor')
        .where(row_timestamp >= ts_start)
        .where(row_timestamp < ts_end)
        .where(F.col('is_pageview')==True)
        ## agent-type user to filter spiders
        ## https://meta.wikimedia.org/wiki/Research:Page_view/Tags#Spider
        .where(F.col('agent_type') == "user")
        ## user: desktop/mobile/mobile app; isaac filters != mobile app
        .where(F.col('access_method') != "mobile app")
        ## only wikis
        .where(F.col('normalized_host.project_family')=='wikipedia')
        ## only namespace 0
        .where( F.col('namespace_id') == 0 )
        .withColumn('wiki_db', F.concat(F.col('normalized_host.project'),F.lit('wiki')) )
    )
    ## filter only specific wiki (or all if wiki_db=='wikidata')
    if wiki_db == 'wikidata':
        pass
    else:
        df_actor = df_actor.where(F.col('wiki_db')==wiki_db)

    ## checkpoint for inspecting table
    # df_actor.limit(10).write.mode('overwrite').parquet('/user/mgerlach/sessions/test.parquet')

    # filter maximum and minimum pageviews per user
    # n_p is the number of pageviews per actor per day (across projects)
    df_actor = (
        df_actor
        .withColumn('n_p', F.sum(F.lit(1)).over(w_p) )
        .where(F.col('n_p') >= n_p_min)
        .where(F.col('n_p') <= n_p_max)
    )

    ## join the wikidata-item to each pageview
    ## we keep only pageviews for which we have a correpsionding wikidata-item id

    ## table with mapping wikidata-ids to page-ids
    ## partition wikidb and page-id ordered by snapshot
    w_wd = Window.partitionBy(F.col('wiki_db'),F.col('page_id')).orderBy(F.col('snapshot').desc())
    df_wd = (
        spark.read.table('wmf.wikidata_item_page_link')
        ## snapshot: this is a partition!
        .where(F.col('snapshot') >= '2020-07-01') ## resolve issues with non-mathcing wikidata-items
        ## only wikis (enwiki, ... not: wikisource)
        .where(F.col('wiki_db').endswith('wiki'))
    )
    ## filter only specific wiki (or all if wiki_db=='wikidata')
    if wiki_db == 'wikidata':
        pass
    else:
        df_wd = df_wd.where(F.col('wiki_db')==wiki_db)
    ## get the most recent wikidata-item for each pid+wikidb
    df_wd = (
        df_wd
        .withColumn('item_id_latest',F.first(F.col('item_id')).over(w_wd))
        .select(
            'wiki_db',
            'page_id',
            F.col('item_id_latest').alias('item_id')
        )
        .drop_duplicates()
    )
    df_actor_wd = (
        df_actor
        .join(
            df_wd,
            on = ['page_id','wiki_db'],
            how='inner'
        )
    )

    ## aggregate all pageviews with same actor-signature across wikis to get sessions
    df_actor_wd_agg = (
        df_actor_wd
        .groupby('actor_signature_per_project_family')
        .agg(
             F.first(F.col('access_method')).alias('access_method'), ## this could change along a session
             F.first(F.col('geocoded_data')).alias('geocoded_data'),
    #              F.first(F.col('n_p_by_user')).alias('session_length'),
             F.array_sort(
                 F.collect_list(
                     F.struct(
                         F.col('ts'),
                         F.col('page_id'),
                         F.col('pageview_info.page_title').alias('page_title'),
                         F.col('wiki_db'),
                         F.col('item_id').alias('qid'),
                     )
                 )
             ).alias('session')
         )
    )
    # df_actor_wd_agg.limit(10).write.mode('overwrite').parquet('/user/mgerlach/sessions/test.parquet')


    ## apply filter to the sessions
    try:
        os.mkdir(path_save)
    except FileExistsError:
        pass
    PATH_TMP = os.path.join(path_save,'tmp')
    try:
        os.mkdir(PATH_TMP)
    except FileExistsError:
        pass

    ## hdfs-storing, some temporary files which will be deleted later
    output_hdfs_dir = os.path.join(base_dir_hdfs,filename_save)
    os.system('hadoop fs -rm -r %s'%output_hdfs_dir)
    ## local storing
    base_dir_local =  path_save
    output_local_dir_tmp = os.path.join(base_dir_local,'tmp',filename_save)
    output_local_file = os.path.join(base_dir_local,filename_save)

    ## load data
    # requests = spark.read.load(filename).rdd.map(lambda x: x['session'])
    requests = df_actor_wd_agg.rdd.map(lambda x: x['session'])
    ## keep only pageviews from a language
    requests = requests.map(lambda rs: [r for r in rs if r['page_id'] != None])
    to_str = lambda x: ' '.join([str(e['page_id']) for e in x])

    (requests
     .map(parse_requests)
     .filter(filter_blacklist_qid) ## remove main_page
     .filter(lambda x: len(x)>=nlen_min) ## only sessions with at least length nlen_min
     .map(filter_consecutive_articles) ## remove consecutive calls to same article
     .filter(lambda x: len(x)>=nlen_min) ## only sessions with at least length nlen_min
     .flatMap(lambda x: sessionize(x, dt = dt)) ## break sessions if interevent time is too large
     .filter(lambda x: len(x)>=nlen_min) ## only sessions with at least length nlen_min
     .filter(lambda x: len(x)<=nlen_max) ## only sessions with at most length nlen_max
     .map(to_str) ## conctenate session as single string
     ## write to hdfs
     .saveAsTextFile(output_hdfs_dir,compressionCodecClass = "org.apache.hadoop.io.compress.GzipCodec")

    )

    ## copy to local (set of tmp-dirs)
    os.system('hadoop fs -copyToLocal %s %s'%(output_hdfs_dir,output_local_dir_tmp))
    ## concatenate and unzip into single file
    os.system('cat %s/* | gunzip > %s'%(output_local_dir_tmp,output_local_file))
    # ## remove set of tmp-dirs
    os.system('rm -rf %s'%output_local_dir_tmp)
    # ## remove hadoop data
    os.system('hadoop fs -rm -r %s'%output_hdfs_dir)

    print('Path to reading sessions: %s'%filename_save)
    return filename_save
##############################################
## some helper functions for session filtering
##############################################

## defining filter and maps
def parse_requests(requests):
    """
    do some initial parsing:
    - drop pages without timestamp (we dont know which order)
    """
    requests_clean = []
    for r in requests:
        if r['ts'] == None:
            pass
        else:
            requests_clean += [r]
    return requests_clean

def filter_consecutive_articles(requests):
    """
    Looking at the data, there are a lot of
    sessions with the same article
    requested 2 times in a row. This
    does not make sense for training, so
    lets collapse them into 1 request.
    We compare qids
    """
    r = requests[0]
    t = r['page_id']
    clean_rs = [r,]
    prev_t = t
    for r in requests[1:]:
        t = r['page_id']
        if t == prev_t:
            continue
        else:
            clean_rs.append(r)
            prev_t = t
    return clean_rs

def filter_blacklist_qid(requests):
    """
    If the session contains an article in the blacklist,
    drop the session. Currently, only the Main Page is
    in the black list
    """

    black_list = set(['Q5296',])
    for r in requests:
        if r['qid'] in black_list:
            return False
    return True


def sessionize(requests, dt = 3600):
    """
    Break request stream whenever
    there is a gap larger than dt [secs] in requests.
    default is 3600s=1hour [from Halfaker et al. 2015]
    """
    sessions = []
    session = [requests[0]]
    for r in requests[1:]:
        d = r['ts'] -  session[-1]['ts']
        if d > datetime.timedelta(seconds=dt):
            sessions.append(session)
            session = [r,]
        else:
            session.append(r)

    sessions.append(session)
    return sessions


if __name__ == "__main__":
    main()