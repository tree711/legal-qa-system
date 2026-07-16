import unittest
from unittest.mock import Mock, patch

from agent import RetrievalAgent, SummaryAgent


MOCK_RESPONSE = {
    "query": "劳动合同试用期最长可以约定多久？",
    "results": [
        {
            "law_name": "中华人民共和国劳动法(2018修正)",
            "article_no": "第二十一条",
            "content": "劳动合同可以约定试用期。试用期最长不得超过六个月。",
            "chapter": "第三章劳动合同和集体合同",
            "source_url": "crawler/lawhtml/labor_law_pkulaw.html",
            "score": 0.8217784762382507,
        },
        {
            "law_name": "中华人民共和国劳动合同法(2012修正)",
            "article_no": "第十九条",
            "content": "劳动合同期限不同，试用期上限分别为一个月、二个月或六个月。",
            "chapter": "第二章劳动合同的订立",
            "source_url": "crawler/lawhtml/labor_contract_law_pkulaw.html",
            "score": 0.7980366349220276,
        },
        {
            "law_name": "示例低分法规",
            "article_no": "第一条",
            "content": "低分参考内容。",
            "chapter": "第一章",
            "source_url": "example.html",
            "score": 0.55,
        },
    ],
}


class TestRetrievalAgent(unittest.TestCase):
    @patch("agent.retrieval_agent.requests.post")
    def test_retrieve_success(self, mock_post: Mock) -> None:
        response = Mock()
        response.json.return_value = MOCK_RESPONSE
        response.raise_for_status.return_value = None
        mock_post.return_value = response

        agent = RetrievalAgent(score_threshold=0.6)
        result = agent.retrieve("劳动合同试用期最长可以约定多久？")

        self.assertEqual(result["status"], "success")
        self.assertEqual(len(result["results"]), 3)
        self.assertEqual(len(result["trusted_results"]), 2)
        self.assertEqual(len(result["reference_results"]), 1)
        self.assertTrue(result["trusted_results"][0]["trusted"])
        self.assertFalse(result["reference_results"][0]["trusted"])

        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        self.assertEqual(
            kwargs["json"],
            {"query": "劳动合同试用期最长可以约定多久？"},
        )

    def test_empty_question(self) -> None:
        result = RetrievalAgent().retrieve("   ")
        self.assertEqual(result["status"], "error")
        self.assertIn("不能为空", result["message"])


class TestSummaryAgent(unittest.TestCase):
    def test_summary_success(self) -> None:
        retrieval_result = {
            "status": "success",
            "question": MOCK_RESPONSE["query"],
            "trusted_results": [
                {
                    **MOCK_RESPONSE["results"][0],
                    "trusted": True,
                },
                {
                    **MOCK_RESPONSE["results"][1],
                    "trusted": True,
                },
            ],
            "reference_results": [],
        }

        result = SummaryAgent().summarize(retrieval_result)

        self.assertEqual(result["status"], "success")
        self.assertEqual(len(result["references"]), 2)
        self.assertIn("中华人民共和国劳动法", result["summary"])
        self.assertIn("第十九条", result["summary"])


if __name__ == "__main__":
    unittest.main()
