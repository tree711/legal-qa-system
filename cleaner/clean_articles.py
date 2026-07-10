import json
import re
from pathlib import Path


RAW_DIR = Path("data/raw")
CLEAN_DIR = Path("data/clean")
OUTPUT_FILE = CLEAN_DIR / "cleaned_articles.json"


def clean_text(text: str) -> str:
    """
    基础文本清洗：
    1. 去掉多余空白、换行、制表符
    2. 去掉北大法宝网页残留信息
    3. 去掉中文之间不必要的空格
    4. 去掉标点前多余空格
    """
    if not text:
        return ""

    text = str(text)

    # 统一空白
    text = text.replace("\u3000", " ")
    text = re.sub(r"\s+", " ", text)

    # 去掉北大法宝网页残留信息
    garbage_patterns = [
        r"新旧对照.*$",
        r"本条变迁.*$",
        r"编辑精选.*$",
        r"法宝新AI.*$",
        r"法宝联想.*$",
    ]

    for pattern in garbage_patterns:
        text = re.sub(pattern, "", text)

    # 去掉中文之间多余空格，例如 “根据 宪法” -> “根据宪法”
    text = re.sub(r"(?<=[\u4e00-\u9fa5])\s+(?=[\u4e00-\u9fa5])", "", text)

    # 去掉标点前多余空格，例如 “宪法 ，” -> “宪法，”
    text = re.sub(r"\s+([，。；：、！？,.!?])", r"\1", text)

    return text.strip()


def clean_article_content(content: str, article_no: str) -> str:
    """
    条文正文清洗：
    1. 基础清洗
    2. 去掉正文开头重复的条号
       例如：
       “第一条 为了保护……” -> “为了保护……”
    """
    content = clean_text(content)
    article_no = clean_text(article_no)

    if article_no:
        pattern = r"^" + re.escape(article_no) + r"\s*"
        content = re.sub(pattern, "", content).strip()

    return content


def build_article_id(file_stem: str, index: int) -> str:
    """
    自动生成唯一 ID。
    例如：
    civil_code_0001
    labor_contract_law_0001
    criminal_law_0001
    """
    return f"{file_stem}_{index:04d}"


def normalize_one_file(file_path: Path) -> list:
    """
    将单个 raw 法律 JSON 转成统一条文格式。
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

    raw_files = sorted(RAW_DIR.glob("*.json"))

    if not raw_files:
        print(f"[错误] 未找到 raw JSON 文件：{RAW_DIR}")
        return

    print(f"发现 raw 法律文件数量：{len(raw_files)}\n")

    for file_path in raw_files:
        try:
            articles = normalize_one_file(file_path)
            all_articles.extend(articles)
            print(f"[完成] {file_path.name}：清洗出 {len(articles)} 条")
        except Exception as e:
            print(f"[失败] {file_path.name}：{e}")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_articles, f, ensure_ascii=False, indent=2)

    print("\n全部清洗完成")
    print(f"总计清洗条文数：{len(all_articles)}")
    print(f"输出文件：{OUTPUT_FILE}")


if __name__ == "__main__":
    main()