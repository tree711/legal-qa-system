
"""
北大法宝法规完整正文爬虫
修复：
1. 不再使用 hidden input 中的 Title 作为正文
2. 根据 tiao_x 锚点提取完整法条内容
3. 保留目录摘要 directory_summary
"""

import argparse
import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup


DEFAULT_URL = "https://www.pkulaw.com/"


class PKULawCrawler:

    def __init__(self, cookie: str = ""):
        self.headers = {
            "User-Agent":
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/124 Safari/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9"
        }
        if cookie:
            self.headers["Cookie"] = cookie

    def fetch_html(self, url):
        r = requests.get(url, headers=self.headers, timeout=30)
        r.raise_for_status()
        r.encoding = r.apparent_encoding
        return r.text

    def read_html_file(self, path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def _clean_text(self, text):
        return re.sub(r"\s+", " ", text or "").strip()

    def _try_parse_json(self, value):
        value = value.strip()
        if not value.startswith("{"):
            return None
        try:
            return json.loads(value)
        except:
            try:
                return json.loads(
                    value.replace("&quot;", '"')
                )
            except:
                return None

    def extract_hidden_law_json(self, soup):
        result = []

        for x in soup.find_all("input", {"type": "hidden"}):
            data = self._try_parse_json(
                x.get("value", "")
            )
            if (
                isinstance(data, dict)
                and isinstance(data.get("Data"), list)
            ):
                result.append(data)

        if not result:
            raise Exception("没有找到法规目录JSON")

        result.sort(
            key=lambda x: len(str(x.get("Data"))),
            reverse=True
        )

        return result[0]

    def flatten_nodes(self, nodes, parent=""):
        output = []

        for node in nodes:

            title = self._clean_text(
                str(node.get("Title", ""))
            )

            children = node.get("Data") or []

            if children:

                output.append({
                    "type": "chapter",
                    "name": node.get("Name", ""),
                    "title": title,
                    "content": "",
                    "parent": parent
                })

                output.extend(
                    self.flatten_nodes(
                        children,
                        title
                    )
                )

            else:

                m = re.match(
                    r"^(第[一二三四五六七八九十百零〇]+条)\s*(.*)$",
                    title
                )

                if m:
                    output.append({
                        "type": "article",
                        "name": node.get("Name", ""),
                        "article_no": m.group(1),
                        "title": m.group(1),
                        "directory_summary": m.group(2),
                        "content": "",
                        "parent": parent
                    })

        return output

    def extract_full_articles(self, soup):

        contents = {}

        anchors = soup.find_all(
            "a",
            attrs={
                "name": re.compile(
                    r"^tiao_\d+$"
                )
            }
        )

        for anchor in anchors:

            name = anchor.get("name")

            texts = []

            for e in anchor.next_elements:

                if (
                    getattr(e, "name", None) == "a"
                    and e != anchor
                    and re.match(
                        r"^tiao_\d+$",
                        e.get("name", "")
                    )
                ):
                    break

                if isinstance(e, str):

                    t = self._clean_text(e)

                    if t:
                        texts.append(t)

            text = self._clean_text(
                " ".join(texts)
            )

            contents[name] = text

        return contents


    def parse(self, html, url=""):

        soup = BeautifulSoup(
            html,
            "lxml"
        )

        title_node = soup.find(
            "input",
            {"id": "ArticleTitle"}
        )

        title = ""

        if title_node:
            title = title_node.get(
                "value",
                ""
            )

        tree = self.extract_hidden_law_json(
            soup
        )

        items = self.flatten_nodes(
            tree["Data"]
        )

        full = self.extract_full_articles(
            soup
        )

        for item in items:

            if item["type"] == "article":

                item["content"] = full.get(
                    item["name"],
                    item["directory_summary"]
                )

        articles = [
            x for x in items
            if x["type"] == "article"
        ]

        return {
            "title": title,
            "source": "北大法宝",
            "url": url,
            "crawl_time":
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            "article_count":
                len(articles),
            "items": items,
            "articles": articles
        }


    def save_json(self, data, path):

        os.makedirs(
            os.path.dirname(path),
            exist_ok=True
        )

        with open(
            path,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                data,
                f,
                ensure_ascii=False,
                indent=2
            )


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--html-file",
        default=""
    )

    parser.add_argument(
        "--url",
        default=DEFAULT_URL
    )

    parser.add_argument(
        "--output",
        default="data/raw/law.json"
    )

    parser.add_argument(
        "--cookie",
        default=""
    )

    args = parser.parse_args()

    crawler = PKULawCrawler(
        args.cookie
    )

    if args.html_file:
        html = crawler.read_html_file(
            args.html_file
        )
        url = args.html_file
    else:
        html = crawler.fetch_html(
            args.url
        )
        url = args.url

    data = crawler.parse(
        html,
        url
    )

    crawler.save_json(
        data,
        args.output
    )

    print("完成")
    print("法条数量:", data["article_count"])

    for x in data["articles"][:3]:
        print(
            x["article_no"],
            x["content"]
        )


if __name__ == "__main__":
    main()
