from sqlitedict import SqliteDict
import xgboost as xgb

from src.scripts.utils import process_page
import multiprocessing


class Query:
    def __init__(self, logger):
        self.logger = logger

    def run(self, wikitext: str, page_title: str, pageid: int, revid: int, lang: str, threshold: float) -> dict:
        self.logger.info(
            'Getting link recommendations for article %s in %swiki with link-threshold %s' %
            (page_title, lang, threshold))
        self.logger.info('Loading the trained model')
        try:
            anchors = SqliteDict("./data/{0}/{0}.anchors.sqlite".format(lang))
            page_ids = SqliteDict("./data/{0}/{0}.pageids.sqlite".format(lang))
            redirects = SqliteDict("./data/{0}/{0}.redirects.sqlite".format(lang))
            word2vec = SqliteDict("./data/{0}/{0}.w2v.filtered.sqlite".format(lang))
            nav2vec = SqliteDict("./data/{0}/{0}.nav.filtered.sqlite".format(lang))
            n_cpus_max = min([int(multiprocessing.cpu_count() / 4), 8])
            model = xgb.XGBClassifier(n_jobs=n_cpus_max)  # init model
            model.load_model("./data/{0}/{0}.linkmodel_v2.bin".format(lang))
        except BaseException:
            message = 'Could not open trained model in %swiki. try another language.' % lang
            self.logger.error(message)
            return {'error': message}

        self.logger.info('Processing wikitext to get link recommendations')
        try:
            added_links = process_page(
                wikitext,
                page_title,
                anchors,
                page_ids,
                redirects,
                word2vec,
                nav2vec,
                model,
                threshold=threshold,
                return_wikitext=False)
        except BaseException:
            message = """Not able to process article '%s' in %swiki. try another article.""" % (page_title, lang)
            self.logger.error(message)
            return {'error': message}

        try:
            anchors.close()
            page_ids.close()
            redirects.close()
            word2vec.close()
            nav2vec.close()
        except BaseException:
            message = 'Could not close model in %swiki.' % lang
            self.logger.warning(message)
            return {'error': message}

        self.logger.info('Number of links from recommendation model: %s' % len(added_links))
        return {
            'page_title': page_title,
            'lang': lang,
            'pageid': pageid,
            'revid': revid,
            'no_added_links': len(added_links),
            'added_links': added_links,
        }
