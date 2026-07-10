import json
import re
from pathlib import Path


RAW_DIR = Path("data/raw")
CLEAN_DIR = Path("data/clean")

INPUT_FILES = [
    "civil_code.json",
    "labor_contract_law.json",
    "labor_law.json",
]

OUTPUT_FILE = CLEAN_DIR / "cleaned_articles.json"


def clean_text(text: str) -> str:
    """
    清洗普通文本：
    1. 去掉多余空白
    2. 去掉网页残留字段
    3. 去掉中文之间不必要的空格
    """
    if not text:
        return ""

    text = text.replace("\u3000", " ")
    text = re.sub(r"\s+", " ", text)

    # 去掉北大法宝网页残留信息
    # 例如：新旧对照 本条变迁 编辑精选 法宝新AI
    garbage_patterns = [
        r"新旧对照.*$",
        r"本条变迁.*$",
        r"编辑精选.*$",
        r"法宝新AI.*$",
    ]

    for pattern in garbage_patterns:
        text = re.sub(pattern, "", text)

    # 去掉中文之间多余空格，例如 “根据 宪法” -> “根据宪法”
    text = re.sub(r"(?<=[\u4e00-\u9fa5])\s+(?=[\u4e00-\u9fa5])", "", text)

    return text.strip()


def clean_article_content(content: str, article_no: str) -> str:
    """
    专门清洗条文正文：
    1. 先进行基础清洗
    2. 去掉正文开头重复的条号
       例如：“第一条 为了保护……” -> “为了保护……”
    """
    content = clean_text(content)

    if article_no:
        article_no = clean_text(article_no)

        # 去掉开头重复条号
        # 支持：
        # 第一条 为了……
        # 第一条　为了……
        # 第一条为了……
        pattern = r"^" + re.escape(article_no) + r"\s*"
        content = re.sub(pattern, "", content).strip()

    return content


def build_article_id(file_stem: str, index: int) -> str:
    """
    自动生成唯一 ID。
    例如：
    civil_code_0001
    labor_contract_law_0001
    labor_law_0001
    """
    return f"{file_stem}_{index:04d}"


def normalize_one_file(file_path: Path) -> list:
    """
    将单个原始法律 JSON 转成统一条文格式。
    """
    with open(file_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    law_name = clean_text(raw_data.get("title", ""))
    source_url = clean_text(raw_data.get("url", ""))
    items = raw_data.get("items", [])

    file_stem = file_path.stem
    cleaned_articles = []

    article_index = 1

    for item in items:
        if item.get("type") != "article":
            continue

        article_no = clean_text(item.get("article_no", ""))
        content = clean_article_content(item.get("content", ""), article_no)
        chapter = clean_text(item.get("parent", ""))

        if not article_no or not content:
            continue

        article = {
            "id": build_article_id(file_stem, article_index),
            "title": f"{law_name} {article_no}",
            "law_name": law_name,
            "article_no": article_no,
            "content": content,
            "chapter": chapter,
            "source_url": source_url,
        }

        cleaned_articles.append(article)
        article_index += 1

    return cleaned_articles


def main():
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)

    all_articles = []

    for file_name in INPUT_FILES:
        file_path = RAW_DIR / file_name

        if not file_path.exists():
            print(f"[跳过] 文件不存在：{file_path}")
            continue

        articles = normalize_one_file(file_path)
        all_articles.extend(articles)

        print(f"[完成] {file_name}：清洗出 {len(articles)} 条")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_articles, f, ensure_ascii=False, indent=2)

    print(f"\n总计清洗条文数：{len(all_articles)}")
    print(f"输出文件：{OUTPUT_FILE}")


if __name__ == "__main__":
    main()