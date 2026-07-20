# 北大法宝网页结构分析

## 1. 页面类型
法规详情页。

示例：
https://www.pkulaw.com/chl/{gid}.html
---

## 2. 页面主要字段
### 法规标题

HTML:
<input id="ArticleTitle">

value:
中华人民共和国劳动合同法(2012修正)

### 法规ID
HTML:
<input id="ArticleId">

### 法规正文
正文不是普通HTML文本。

存储形式：
<input type="hidden">

value字段：
JSON字符串。

结构：
{
 Status:0,
 Data:[
    {
      Title:"第一章 总则",
      Data:[
          {
            Title:"第一条 xxx"
          }
      ]
    }
 ]
}

---
## 3. 解析流程

HTML
↓
BeautifulSoup
↓
搜索hidden input
↓
提取value
↓
json.loads()
↓
递归展开章节
↓
生成标准JSON
---

## 4. 输出字段


|字段|说明|
|-|-|
|title|法律名称|
|source|来源|
|article_count|法条数量|
|articles|法条列表|