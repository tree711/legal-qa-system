#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import sys
from pathlib import Path

path = Path(sys.argv[1] if len(sys.argv) > 1 else "data/test/test_samples_part2.json")
data = json.loads(path.read_text(encoding="utf-8"))
required = {"question", "expected_answer", "retrieved_text", "model_output", "evaluation_note"}
errors = []
for i, row in enumerate(data, 1):
    if set(row) != required:
        errors.append(f"第{i}条字段错误：{set(row)}")
    for key in required:
        if not isinstance(row.get(key), str):
            errors.append(f"第{i}条 {key} 不是字符串")
questions = [x["question"] for x in data]
duplicates = sorted({q for q in questions if questions.count(q) > 1})
print(f"样本数：{len(data)}")
print(f"已有检索结果：{sum(bool(x['retrieved_text'].strip()) for x in data)}")
print(f"已有模型回答：{sum(bool(x['model_output'].strip()) for x in data)}")
print(f"重复问题数：{len(duplicates)}")
if duplicates:
    print("重复问题：")
    for q in duplicates:
        print("-", q)
if errors:
    print("校验失败：")
    for e in errors:
        print("-", e)
    raise SystemExit(1)
if len(data) != 70:
    print("警告：Day3 文件应累计70条。")
    raise SystemExit(1)
print("JSON结构校验通过。")
