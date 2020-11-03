import xgboost as xgb
from src.scripts.utils import process_page
from src.DatasetLoader import DatasetLoader
import multiprocessing


class Query:
    def __init__(self, logger, datasetloader: DatasetLoader):
        self.logger = logger
        self.datasetloader = datasetloader
        n_cpus_max = min([int(multiprocessing.cpu_count() / 4), 8])
        self.model = xgb.XGBClassifier(n_jobs=n_cpus_max)

    def run(self, wikitext: str, page_title: str, pageid: int, revid: int, lang: str, threshold: float) -> dict:
        self.logger.info(
            'Getting link recommendations for article %s in %swiki with link-threshold %s' %
            (page_title, lang, threshold))

        self.logger.info('Loading the trained model')
        self.model.load_model("./model/{0}.bin".format(lang))

        self.logger.info('Processing wikitext to get link recommendations')
        added_links = process_page(
            wikitext,
            page_title,
            self.datasetloader.get('anchors'),
            self.datasetloader.get('pageids'),
            self.datasetloader.get('redirects'),
            self.datasetloader.get('word2vec'),
            self.datasetloader.get('nav2vec'),
            self.model,
            threshold=threshold,
            return_wikitext=False)

        self.logger.info('Number of links from recommendation model: %s' % len(added_links))
        return {
            'page_title': page_title,
            'lang': lang,
            'pageid': pageid,
            'revid': revid,
            'no_added_links': len(added_links),
            'added_links': added_links,
        }
