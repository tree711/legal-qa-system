import unittest

from embedding.search import rerank_legal_articles


def article(article_no: str, score: float) -> dict:
    return {"law_name": "示例法", "article_no": article_no, "content": "示例", "score": score}


class TestLegalRerank(unittest.TestCase):
    def test_contract_formation_promotes_article_483(self) -> None:
        results = rerank_legal_articles(
            "采用要约、承诺方式订立合同时，合同通常在何时成立？",
            [article("第四百八十二条", 0.78), article("第四百八十三条", 0.61)],
        )
        self.assertEqual(results[0]["article_no"], "第四百八十三条")

    def test_unpaid_wages_termination_promotes_article_38(self) -> None:
        results = rerank_legal_articles(
            "公司长期拖欠工资，劳动者能否解除劳动合同？",
            [article("第三十七条", 0.80), article("第三十八条", 0.62)],
        )
        self.assertEqual(results[0]["article_no"], "第三十八条")


if __name__ == "__main__":
    unittest.main()
