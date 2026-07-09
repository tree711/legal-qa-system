# 北大法宝法律法规爬虫模块说明
## 项目结构
```text
legal-qa-system/
├── crawler/                       # 北大法宝爬虫代码
│   ├── pkulaw_crawler.py          # 爬虫主程序
│   └── lawhtml/                   # 原始 HTML 文件
│
├── cleaner/                       # 数据清洗（后续添加）
├── embedding/                     # 组长：向量化（后续添加）
├── rag/                           # RAG 检索模块（后续添加）
├── api/                           # FastAPI 接口（后续添加）
├── data/                          # 数据目录
│   └── raw/                       # B/C组生成的原始 JSON
│
├── docs/
│   └── structure.md               # 北大法宝网页结构分析
│
└── README.md                      # 项目说明
```
## 1. 模块说明
本模块负责从北大法宝法规详情页解析法律条文。
对应项目成员：
- B：网页结构分析 + 爬虫开发
- C：调用本模块批量爬取多部法律

## 2. 环境安装
Python
安装依赖：
pip install requests beautifulsoup4 lxml

## 3. 使用方法 解析已经保存的HTML
步骤：
1. 浏览器打开北大法宝法规详情页
2. 另存为HTML
例如：
crawler/lawhtml/labor_contract_law_pkulaw.html
3. 执行命令：

python crawler/pkulaw_crawler.py --html-file crawler/lawhtml/labor_contract_law_pkulaw.html --output data/raw/labor_contract_law.json

输出：
[OK] 爬取/解析完成
标题：
中华人民共和国劳动合同法(2012修正)
法条数量：
98

## 4. C成员批量使用方法
无需修改解析代码。
准备多个HTML文件：（最好文件名不要中文！）
crawler/lawhtml/
├── xxxx.html
├── 劳动法.html
├── 民法典.html
然后循环调用：

python crawler/pkulaw_crawler.py --html-file crawler/lawhtml/xxxx.html --output data/raw/xxxx.json

最终生成：
劳动合同法.json
劳动法.json
民法典.json
供D组清洗处理。

## 5. 输出JSON格式
{
"title":"",
"source":"北大法宝",
"article_count":98,
"articles":[
 {
  "article_no":"第一条",
  "content":"..."
 }
]
}

