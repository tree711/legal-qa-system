"""
成员B：北大法宝法规详情页单页爬虫
功能：
1. 请求北大法宝法规详情页 URL
2. 从 HTML hidden input 中提取法规目录/条文 JSON
3. 展平章节与法条
4. 保存为 JSON，供 C 组批量爬取、D 组清洗使用

用法：
python crawler/pkulaw_crawler.py --url "https://www.pkulaw.com/chl/xxxx.html" --output data/raw/labor_contract_law.json

示例：
python crawler/pkulaw_crawler.py --url "https://www.pkulaw.com/chl/xxxx.html" --output data/raw/law.json
"""

import argparse
import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup


DEFAULT_URL = "https://www.pkulaw.com/chl/7ab5e7d605f859e6bdfb.html?keyword=%E4%B8%AD%E5%8D%8E%E4%BA%BA%E6%B0%91%E5%85%B1%E5%92%8C%E5%9B%BD%E5%8A%B3%E5%8A%A8%E5%90%88%E5%90%8C%E6%B3%95&way=listView"


class PKULawCrawler:
    def __init__(self, cookie: str = "") -> None:
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://www.pkulaw.com/",
        }
        if cookie:
            self.headers["Cookie"] = cookie

    def fetch_html(self, url: str) -> str:
        response = requests.get(url, headers=self.headers, timeout=20)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or "utf-8"
        return response.text

    def read_html_file(self, html_file: str) -> str:
        with open(html_file, "r", encoding="utf-8") as f:
            return f.read()

    def _try_parse_json(self, value: str) -> Optional[Dict[str, Any]]:
        value = value.strip()
        if not value:
            return None
        if not (value.startswith("{") and "Data" in value and "Title" in value):
            return None
        try:
            data = json.loads(value)
        except json.JSONDecodeError:
            # 部分网页可能在属性中出现转义或多余字符，做一次保守修复
            fixed = value.replace("&quot;", '"').replace("&#34;", '"')
            try:
                data = json.loads(fixed)
            except json.JSONDecodeError:
                return None
        if isinstance(data, dict) and isinstance(data.get("Data"), list):
            return data
        return None

    def extract_hidden_law_json(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """从所有 hidden input 的 value 中寻找包含 Status/Data/Title 的法规 JSON。"""
        candidates: List[Dict[str, Any]] = []
        for input_tag in soup.find_all("input", {"type": "hidden"}):
            value = input_tag.get("value", "")
            parsed = self._try_parse_json(value)
            if parsed:
                candidates.append(parsed)

        if not candidates:
            raise ValueError(
                "没有在 hidden input 中找到法规 JSON。可能原因：页面需要登录、正文由接口异步加载，或网页结构已变化。"
            )

        # 选择 Data 项最多的候选，一般就是法规正文目录树
        candidates.sort(key=lambda x: len(str(x.get("Data", []))), reverse=True)
        return candidates[0]

    def _clean_text(self, text: str) -> str:
        text = re.sub(r"\s+", " ", text or "").strip()
        return text

    def _flatten_nodes(self, nodes: List[Dict[str, Any]], parent: str = "") -> List[Dict[str, str]]:
        results: List[Dict[str, str]] = []
        for node in nodes:
            title = self._clean_text(str(node.get("Title", "")))
            number = str(node.get("Number", "")).strip()
            tier = str(node.get("Tier", "")).strip()
            children = node.get("Data") or []

            # 有子节点的一般是“第一章 总则”等章节；无子节点的一般是具体法条
            if children:
                chapter_name = title
                results.append({
                    "type": "chapter",
                    "number": number,
                    "tier": tier,
                    "title": title,
                    "content": "",
                    "parent": parent,
                })
                results.extend(self._flatten_nodes(children, parent=chapter_name))
            else:
                article_no = ""
                content = title
                m = re.match(r"^(第[一二三四五六七八九十百零〇]+条)\s*(.*)$", title)
                if m:
                    article_no = m.group(1)
                    content = m.group(2).strip()
                results.append({
                    "type": "article" if article_no else "item",
                    "number": number,
                    "tier": tier,
                    "article_no": article_no,
                    "title": title,
                    "content": content,
                    "parent": parent,
                })
        return results

    def parse(self, html: str, url: str = "") -> Dict[str, Any]:
        soup = BeautifulSoup(html, "lxml")

        title_input = soup.find("input", {"id": "ArticleTitle"})
        article_id_input = soup.find("input", {"id": "ArticleId"})
        article_url_input = soup.find("input", {"id": "ArticleUrl"})

        title = ""
        if title_input and title_input.get("value"):
            title = title_input.get("value", "").strip()
        elif soup.title:
            title = soup.title.get_text(strip=True)

        law_tree = self.extract_hidden_law_json(soup)
        items = self._flatten_nodes(law_tree.get("Data", []))
        articles = [x for x in items if x.get("type") == "article"]

        return {
            "title": title,
            "source": "北大法宝",
            "url": url or (article_url_input.get("value", "") if article_url_input else ""),
            "article_id": article_id_input.get("value", "") if article_id_input else "",
            "crawl_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_items": len(items),
            "article_count": len(articles),
            "items": items,
            "articles": articles,
        }

    def save_json(self, data: Dict[str, Any], output_path: str) -> None:
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="北大法宝法规详情页单页爬虫")
    parser.add_argument("--url", default=DEFAULT_URL, help="北大法宝法规详情页 URL")
    parser.add_argument("--html-file", default="", help="离线 HTML 文件，用于本地测试")
    parser.add_argument("--output", default="data/raw/labor_contract_law_pkulaw.json", help="输出 JSON 路径")
    parser.add_argument("--cookie", default="", help="可选：从浏览器复制的北大法宝 Cookie，用于登录态访问")
    args = parser.parse_args()

    crawler = PKULawCrawler(cookie=args.cookie)

    if args.html_file:
        html = crawler.read_html_file(args.html_file)
        source_url = args.html_file
    else:
        html = crawler.fetch_html(args.url)
        source_url = args.url

    data = crawler.parse(html, source_url)
    crawler.save_json(data, args.output)

    print("[OK] 爬取/解析完成")
    print("标题：", data["title"])
    print("来源：", data["source"])
    print("法条数量：", data["article_count"])
    print("输出文件：", args.output)
    print("前3条：")
    for article in data["articles"][:3]:
        print(article.get("article_no", ""), article.get("content", "")[:100])


if __name__ == "__main__":
    main()
