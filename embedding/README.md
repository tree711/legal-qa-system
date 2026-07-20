# 向量化 + 检索模块（组长 Day 2）

## 目录结构
```
project_root/
├── embedding/
│   ├── config.py            # 统一配置（模型名、路径等）
│   ├── test_embedding.py    # 1. 测试 Ollama 向量调用
│   ├── build_index.py       # 2. 构建 FAISS 索引
│   ├── search.py            # 3. 检索脚本
│   └── requirements.txt
└── data/
    ├── cleaned_articles.sample.json   # 示例数据（可先用它自测流程）
    ├── cleaned_articles.json          # D 同学交付的真实数据（放这里）
    └── index/                          # build_index.py 生成的索引会存到这里
```

## 今天的执行顺序

### 0. 安装依赖
```bash
pip install -r embedding/requirements.txt
```

### 1. 验证 Ollama 调用是否正常
```bash
python embedding/test_embedding.py
```
必须看到 `✅ 全部测试通过` 才能继续下一步。常见报错：
- `Ollama 服务没有启动` → 先运行 `ollama serve`
- `模型没有拉取` → 运行 `ollama pull nomic-embed-text`

### 2. 构建索引
真实数据到位前，可以先用示例数据跑通整个流程：
```bash
cp data/cleaned_articles.sample.json data/cleaned_articles.json
python embedding/build_index.py
```
等 D 同学交付真实数据后，把文件替换为真实的 `cleaned_articles.json`，重新运行本命令即可。

### 3. 检索测试
```bash
python embedding/search.py
```
进入交互模式后输入问题，例如：
```
请输入问题: 试用期最长可以约定多久？
```
也可以命令行单次查询：
```bash
python embedding/search.py "试用期最长可以约定多久？"
```

## 给 D 同学的数据格式要求
`data/cleaned_articles.json` 需要是一个 JSON 数组，每条数据至少包含
`law_name`（法律名称）、`article_no`（条文编号）、`content`（条文正文）三个字段，
详细格式说明见 `build_index.py` 文件顶部注释，或参考 `data/cleaned_articles.sample.json`。

如果 D 同学的字段名不一样也没关系，只需要改 `build_index.py` 里
`load_articles()` 函数中的字段映射，不用改其他代码。

## 给后续 RAG 模块（第2周）的接口
`search.py` 里提供了一个可以直接 import 的函数：
```python
from search import search
results = search("试用期最长可以约定多久？", top_k=5)
# results 是 list[dict]，每个 dict 包含 law_name / article_no / content / score 等字段
```
第2周写 RAG 时直接调用这个函数拿到相关条文，拼进 prompt 交给 qwen2:7b 生成回答即可。
