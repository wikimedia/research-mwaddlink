import xgboost as xgb
from src.scripts.utils import process_page
from src.DatasetLoader import DatasetLoader
import multiprocessing


class Query:
    def __init__(self, logger, datasetloader: DatasetLoader):
        self.logger = logger
        self.datasetloader = datasetloader
        self.model = xgb.XGBClassifier(n_jobs=min([int(multiprocessing.cpu_count() / 4), 8]))

    def run(self, wikitext: str, page_title: str, pageid: int, revid: int, wiki_id: str, threshold: float) -> dict:
        self.logger.info(
            'Getting link recommendations for article %s in %swiki with link-threshold %s' %
            (page_title, wiki_id, threshold))

        self.logger.info('Loading the trained model')
        self.model.load_model(self.datasetloader.get_model_path())
        anchors = self.datasetloader.get('anchors')
        pageids = self.datasetloader.get('pageids')
        redirects = self.datasetloader.get('redirects')
        word2vec = self.datasetloader.get('w2vfiltered')
        nav2vec = self.datasetloader.get('navfiltered')
        self.logger.info('Processing wikitext to get link recommendations')
        added_links = process_page(
            wikitext=wikitext,
            page=page_title,
            anchors=anchors,
            pageids=pageids,
            redirects=redirects,
            word2vec=word2vec,
            nav2vec=nav2vec,
            model=self.model,
            threshold=threshold,
            return_wikitext=False)

        anchors.close()
        pageids.close()
        redirects.close()
        word2vec.close()
        nav2vec.close()
        self.logger.info('Number of links from recommendation model: %s' % len(added_links))
        return {
            'page_title': page_title,
            'pageid': pageid,
            'revid': revid,
            'no_added_links': len(added_links),
            'added_links': added_links,
        }
