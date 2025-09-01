import xgboost as xgb
from typing import List
from src.scripts.model_utils import get_model_version
from src.scripts import utils, utils_v2
from src.DatasetLoader import DatasetLoader
import multiprocessing
from time import perf_counter


class Query:
    def __init__(self, logger, datasetloader: DatasetLoader):
        # Increment this version only for major changes in the output format.
        self.format_version = 1
        self.logger = logger
        self.datasetloader = datasetloader
        self.model = xgb.XGBClassifier(
            n_jobs=min([int(multiprocessing.cpu_count() / 4), 8])
        )
        self.datasets = []
        self.wiki_id = None

    def run(
        self,
        wikitext: str,
        page_title: str,
        pageid: int,
        revid: int,
        wiki_id: str,
        language_code: str,
        threshold: float,
        max_recommendations: int,
        sections_to_exclude: list,
    ) -> dict:
        start = perf_counter()
        self.model.load_model(self.datasetloader.get_model_path()[0])
        anchors = self.datasetloader.get("anchors")
        pageids = self.datasetloader.get("pageids")
        redirects = self.datasetloader.get("redirects")
        word2vec = self.datasetloader.get("w2vfiltered")
        model = self.datasetloader.get("model")
        self.datasets = [anchors, pageids, redirects, word2vec, model]
        self.wiki_id = wiki_id

        if get_model_version(self.model) == "v2":
            response = utils_v2.process_page(
                wikitext=wikitext,
                page=page_title,
                anchors=anchors,
                pageids=pageids,
                redirects=redirects,
                word2vec=word2vec,
                model=self.model,
                wiki_id=wiki_id,
                language_code=language_code,
                threshold=threshold,
                pr=True,
                return_wikitext=False,
                context=10,
                maxrec=max_recommendations,
                sections_to_exclude=sections_to_exclude,
            )
        else:
            response = utils.process_page(
                wikitext=wikitext,
                page=page_title,
                anchors=anchors,
                pageids=pageids,
                redirects=redirects,
                word2vec=word2vec,
                model=self.model,
                language_code=language_code,
                threshold=threshold,
                return_wikitext=False,
                maxrec=max_recommendations,
                sections_to_exclude=sections_to_exclude,
            )

        stop = perf_counter()

        log_data = {
            "suggested_links_count": len(response["links"]),
            "info": response["info"],
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

        return self.make_result(
            page_title=page_title,
            pageid=pageid,
            revid=revid,
            added_links=response["links"],
        )

    def get_query_info(self):
        query_total = 0
        query_detail = {}
        for dataset in self.datasets:
            query_detail[dataset.datasetname] = {}
            query_total += dataset.query_count
            query_detail[dataset.datasetname]["total"] = dataset.query_count
            query_detail[dataset.datasetname]["details"] = dataset.query_details
        return query_total, query_detail

    def make_result(
        self, page_title: str, pageid: int, revid: int, added_links: List[dict]
    ):
        return {
            "page_title": page_title,
            "pageid": pageid,
            "revid": revid,
            "links_count": len(added_links),
            "meta": {
                "format_version": self.format_version,
                "dataset_checksums": self.get_dataset_checksums(),
            },
            "links": [
                self.make_link(link, pos)
                for pos, link in enumerate(added_links, start=0)
            ],
        }

    def get_dataset_checksums(self) -> dict:
        """
        :return: Dictionary with dataset names as the keys and their stored checksums as the values.
        """
        checksum_detail = {}
        datasets = self.datasets
        checksums = self.datasetloader.get("checksum")
        if self.datasetloader.backend != "mysql":
            return checksum_detail
        for dataset in datasets:
            checksum_detail[dataset.datasetname] = checksums[
                "%s_%s" % (self.wiki_id, dataset.datasetname)
            ]
        return checksum_detail

    def make_link(self, link: dict, pos: int):
        return {
            "link_text": link["link_text"],
            "wikitext_offset": link["start_offset"],
            "context_before": link["context_plaintext"][0],
            "context_after": link["context_plaintext"][1],
            "link_target": link["link_target"],
            "match_index": link["match_index"],
            "score": link["score"],
            "link_index": pos,
        }
