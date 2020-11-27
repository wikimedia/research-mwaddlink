import xgboost as xgb
from src.scripts.utils import process_page
from src.DatasetLoader import DatasetLoader
import multiprocessing
from time import perf_counter


class Query:
    def __init__(self, logger, datasetloader: DatasetLoader):
        self.logger = logger
        self.datasetloader = datasetloader
        self.model = xgb.XGBClassifier(
            n_jobs=min([int(multiprocessing.cpu_count() / 4), 8])
        )
        self.datasets = []

    def run(
        self,
        wikitext: str,
        page_title: str,
        pageid: int,
        revid: int,
        wiki_id: str,
        threshold: float,
        max_recommendations: int,
    ) -> dict:

        start = perf_counter()
        self.model.load_model(self.datasetloader.get_model_path())
        anchors = self.datasetloader.get("anchors")
        pageids = self.datasetloader.get("pageids")
        redirects = self.datasetloader.get("redirects")
        word2vec = self.datasetloader.get("w2vfiltered")
        nav2vec = self.datasetloader.get("navfiltered")
        self.datasets = [anchors, pageids, redirects, word2vec, nav2vec]

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
            return_wikitext=False,
            maxrec=max_recommendations,
        )

        anchors.close()
        pageids.close()
        redirects.close()
        word2vec.close()
        nav2vec.close()

        stop = perf_counter()

        log_data = {
            "suggested_links_count": len(added_links),
            "request_parameters": {
                "article_length": len(wikitext),
                "page_title": page_title,
                "pageid": pageid,
                "revid": revid,
                "wiki": wiki_id,
                "threshold": threshold,
                "max_recommendations": max_recommendations,
            },
            "execution_time": stop - start,
        }

        if self.datasetloader.backend == "mysql":
            query_total, query_detail = self.get_query_info()
            log_data["query_count"] = query_total
            log_data["query_count_by_dataset"] = query_detail

        self.logger.info(log_data)

        return {
            "page_title": page_title,
            "pageid": pageid,
            "revid": revid,
            "links_count": len(added_links),
            "links": added_links,
        }

    def get_query_info(self):
        query_total = 0
        query_detail = {}
        for dataset in self.datasets:
            query_detail[dataset.datasetname] = {}
            query_total += dataset.query_count
            query_detail[dataset.datasetname]["total"] = dataset.query_count
            query_detail[dataset.datasetname]["details"] = dataset.query_details
        return query_total, query_detail
