import unittest

from api.main import build_rag_system_prompt


class TestGenerationConstraints(unittest.TestCase):
    def test_prompt_exposes_hard_rule_against_invented_exceptions(self) -> None:
        prompt = build_rag_system_prompt([
            {
                "law_name": "中华人民共和国劳动合同法",
                "article_no": "第十九条",
                "content": "同一用人单位与同一劳动者只能约定一次试用期。",
            }
        ])
        self.assertIn("反例约束", prompt)
        self.assertIn("只能约定一次试用期", prompt)
        self.assertIn("不得自行增加", prompt)


if __name__ == "__main__":
    unittest.main()
