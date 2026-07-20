import unittest

from agent.scheduler import AgentScheduler


class TestUnifiedChatPipeline(unittest.TestCase):
    def test_single_turn_reuses_one_retrieval_result(self):
        calls = {"search": 0, "chat": 0}

        def search_handler(query):
            calls["search"] += 1
            return {"query": query, "results": [{
                "law_name": "示例法", "article_no": "第一条", "content": "示例内容",
                "chapter": "第一章", "source_url": "", "score": 0.9,
            }]}

        def chat_handler(messages, top_k, search_query, retrieval_result):
            calls["chat"] += 1
            self.assertEqual(search_query, "测试问题")
            self.assertEqual(len(retrieval_result["results"]), 1)
            return {
                "answer": "基于同一份检索结果的回答",
                "messages": messages + [{"role": "assistant", "content": "基于同一份检索结果的回答"}],
                "references": retrieval_result["results"],
                "model": "test-model", "elapsed_seconds": 0.01, "low_confidence": False,
            }

        scheduler = AgentScheduler(search_handler=search_handler, chat_handler=chat_handler)
        result = scheduler.chat([{"role": "user", "content": "测试问题"}])

        self.assertTrue(result["success"])
        self.assertEqual(calls, {"search": 1, "chat": 1})
        self.assertEqual(result["references"][0]["law_name"], "示例法")


if __name__ == "__main__":
    unittest.main()
