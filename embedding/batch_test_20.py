"""
batch_test_20.py
测试 20 个覆盖不同法律领域的问题，验证检索召回效果
"""

import json
import sys
from search import search

# 20 个测试问题（按法律领域分类）
TEST_QUERIES = [
    # ===== 劳动法 & 劳动合同法 =====
    "试用期最长可以约定多久？",
    "最低工资标准由谁制定？",
    "加班费怎么计算？",
    "劳动合同应当在什么时候签订？",
    "劳动者在什么情况下可以解除劳动合同？",
    "用人单位在什么情况下可以解除劳动合同？",
    "非全日制用工可以约定试用期吗？",
    "劳动合同应当包含哪些条款？",
    
    # ===== 民法典 =====
    "民事主体在民事活动中的法律地位是什么？",
    "什么情况下合同无效？",
    "人身损害赔偿包括哪些项目？",
    "诉讼时效是多久？",
    "夫妻共同债务如何认定？",
    
    # ===== 刑法 =====
    "什么是正当防卫？",
    "盗窃罪的量刑标准是什么？",
    "什么情况下构成故意伤害罪？",
    
    # ===== 公司法 =====
    "设立有限责任公司需要什么条件？",
    "公司股东有哪些权利？",
    
    # ===== 消费者权益保护法 =====
    "消费者有哪些基本权利？",
    "经营者欺诈消费者要承担什么责任？",
]

def batch_test():
    print("=" * 70)
    print("20 个法律问题批量检索测试")
    print("=" * 70)
    
    results = []
    success_count = 0
    
    for idx, q in enumerate(TEST_QUERIES, 1):
        print(f"\n【问题 {idx}/20】{q}")
        print("-" * 50)
        
        try:
            hits = search(q, top_k=3)
        except Exception as e:
            print(f"  ❌ 检索失败: {e}")
            results.append({"question": q, "top1": None, "top1_title": None, "status": "error"})
            continue
        
        if not hits:
            print("  ⚠️ 无检索结果")
            results.append({"question": q, "top1": None, "top1_title": None, "status": "no_result"})
            continue
        
        # 兼容返回字段名：可能是 'title' 或 '标题'
        first = hits[0]
        top1_title = first.get('title') or first.get('标题', str(first))
        
        # 判断第一条是否相关
        is_relevant = any(law in top1_title for law in [
            "劳动法", "劳动合同法", "民法典", "刑法", "公司法", "消费者权益保护法",
            "社会保险法", "个人信息保护法", "行政处罚法", "民事诉讼法"
        ])
        
        for i, hit in enumerate(hits, 1):
            print(f"  [{i}] 相关度: {hit.get('score', hit.get('相关度', 0)):.4f}")
            hit_title = hit.get('title') or hit.get('标题', '')
            print(f"      {hit_title}")
            content = hit.get('content') or hit.get('内容', '')
            content_preview = content[:70] + "..." if len(content) > 70 else content
            print(f"      {content_preview}")
        
        status = "✅" if is_relevant else "⚠️"
        print(f"  {status} 第一条来自: {top1_title}")
        
        if is_relevant:
            success_count += 1
        
        results.append({
            "question": q,
            "top1_score": first.get('score', first.get('相关度', 0)),
            "top1_title": top1_title,
            "status": "success" if is_relevant else "maybe_irrelevant"
        })
    
    # ===== 统计摘要 =====
    print("\n" + "=" * 70)
    print("统计摘要")
    print("=" * 70)
    print(f"总问题数: 20")
    print(f"✅ 第一条结果相关: {success_count}/20")
    print(f"召回率: {success_count/20*100:.1f}%")
    
    print("\n详细结果:")
    for r in results:
        if r['status'] == "success":
            print(f"  ✅ {r['question'][:20]}... → {r['top1_title']}")
        elif r['status'] == "no_result":
            print(f"  ❌ {r['question'][:20]}... → 无结果")
        elif r['status'] == "error":
            print(f"  ❌ {r['question'][:20]}... → 报错")
        else:
            print(f"  ⚠️ {r['question'][:20]}... → {r['top1_title']}")

if __name__ == "__main__":
    batch_test()