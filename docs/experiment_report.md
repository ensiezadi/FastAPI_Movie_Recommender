<div align="center">

# 信息安全理论与技术实验报告

</div>

&nbsp;

|  |  |
| --- | --- |
| **姓　　名：** | 程浩 |
| **学　　号：** | 241020055 |
| **学　　院：** | 计算机与大数据 |
| **专　　业：** | 信息安全 |
| **年　　级：** | 2024 级 |
| **指导教师：** | 邹剑 |

<div align="center">

## 实验一：基于容器化微服务与电影相似度推荐的系统实现

</div>

---

## 1. 实验目的

本实验面向“云端电影推荐系统”的课程项目 Demo，目标不是只在 Notebook 中验证算法指标，而是构建一个可以在线交互、可部署、可观测、可初步评估的推荐系统原型。

当前系统重点验证以下问题：

1. 能否基于 MovieLens 数据集构建可交互电影推荐服务。
2. 能否复现原始 FastAPI Movie Recommender 仓库的核心能力，即“选择电影并返回相似电影”。
3. 能否在 Web 页面中展示推荐结果、推荐解释、相似度得分和本地点击率。
4. 能否提供离线抽样评估指标，为后续论文或课程报告提供实验依据。

## 2. 实验环境与系统架构

### 2.1 实验环境

| 项目 | 配置 |
| --- | --- |
| 后端服务 | FastAPI |
| 前端展示 | Streamlit |
| 数据库 | PostgreSQL |
| 缓存 | Redis |
| 容器编排 | Docker Compose |
| 数据集 | MovieLens 32M / Latest CSV 格式 |
| 当前导入规模 | 200,948 用户，87,618 电影，32,921,437 评分 |

### 2.2 系统架构

系统采用前后端分离和容器化部署方式：

```text
用户浏览器
  -> Streamlit 前端
  -> FastAPI 推荐服务
  -> Redis 推荐缓存
  -> PostgreSQL 数据库
```

后端提供电影搜索、相似电影推荐、点击统计、系统指标和抽样评估接口。前端分为三个主要页面：

| 页面 | 功能 |
| --- | --- |
| Demo | 搜索电影、选择电影、展示相似电影推荐 |
| Evaluation | 展示 Precision@K、Recall@K、NDCG@K、HitRate@K 和响应延迟 |
| Advanced | 保留后续 ALS/BPR/Hybrid 实验入口 |

## 3. 数据集说明

当前系统已经导入 MovieLens 现代 CSV 数据集，数据库统计如下：

| 表 | 数量 |
| --- | ---: |
| users | 200,948 |
| movies | 87,618 |
| ratings | 32,921,437 |

与 MovieLens 1M 相比，当前数据规模更大，能够更好体现数据库、缓存和服务化部署的必要性。但由于 MovieLens Latest 数据集会随时间更新，因此正式论文固定结果更建议使用 MovieLens 32M 作为稳定 benchmark。

## 4. 推荐方法设计

### 4.1 电影相似推荐

当前 Demo 主流程采用电影到电影的相似推荐方式。用户输入或选择一部电影后，系统基于评分行为计算候选电影与输入电影的相似度。

为保证在 3200 万级评分数据上仍能在线交互，当前实现采用抽样评分向量余弦相似度：

```text
1. 获取输入电影的一部分评分用户；
2. 获取这些用户评分过的其他电影；
3. 在采样用户空间中计算电影评分向量余弦相似度；
4. 返回 Top-K 相似电影。
```

推荐解释示例：

```text
rating cosine: 124 sampled shared users
```

前端将其解释为“相似评分行为”，表示这些电影在共同评分用户上的评分模式较接近。

### 4.2 点击率统计

系统记录本地 Demo 中的推荐曝光和点击：

```text
Demo CTR = clicks / recommendations_shown
```

该指标只表示本地演示点击率，不代表真实线上用户点击率。因此报告中使用 “Demo CTR” 命名，避免与生产环境 CTR 混淆。

### 4.3 冷启动场景

用户可以在侧边栏新增电影，例如输入“战狼”、类型为 `Action|Drama`、初始评分为 3.0。由于 MovieLens 原始数据中不存在《战狼》，该场景应解释为：

```text
模拟新电影加入系统后的冷启动推荐。
```

对于缺少评分历史的新电影，系统无法直接计算可靠的协同过滤相似度，因此只能使用类型、标题和初始评分作为辅助信息。该部分适合作为冷启动案例分析，而不是主推荐效果实验。

## 5. 实验设计

### 5.1 功能实验

功能实验验证系统是否达到原仓库核心能力：

| 功能 | 验收方式 |
| --- | --- |
| 电影搜索 | 输入 `Toy Story` 能检索到 `Toy Story (1995)` |
| 相似推荐 | `GET /recommend/movie?movie_id=1&limit=4` 返回 4 条推荐 |
| 推荐解释 | 每条推荐显示相似原因和 Score |
| 点击统计 | 点击推荐项后 Demo CTR 发生变化 |
| 新增电影 | 侧边栏新增电影后写入数据库 |

### 5.2 抽样离线评估

系统提供轻量级 leave-one-out 抽样评估：

```text
对每个抽样用户：
1. 取一部高评分电影作为 seed movie；
2. 取另一部高评分电影作为 target movie；
3. 用 seed movie 生成 Top-K 推荐；
4. 如果 target movie 出现在 Top-K 中，则记为命中。
```

评估指标包括：

| 指标 | 含义 |
| --- | --- |
| Precision@K | Top-K 推荐中命中目标的比例 |
| Recall@K | 目标电影是否被召回 |
| NDCG@K | 命中位置越靠前得分越高 |
| HitRate@K | 样本用户中至少命中一次的比例 |
| Avg Latency | 平均推荐响应时间 |
| p95 Latency | 95 分位响应时间 |

## 6. 实验结果

### 6.1 功能结果

以 `Toy Story (1995)` 为输入电影，系统能够返回基于评分行为的相似电影推荐。一次接口结果示例如下：

| 推荐电影 | 类型 | Score | 推荐原因 |
| --- | --- | ---: | --- |
| Matrix, The (1999) | Action\|Sci-Fi\|Thriller | 0.3412 | rating cosine: 124 sampled shared users |
| Shawshank Redemption, The (1994) | Drama | 0.3401 | rating cosine: 122 sampled shared users |
| Star Wars: Episode IV - A New Hope (1977) | Action\|Adventure\|Fantasy\|Sci-Fi | 0.3380 | rating cosine: 124 sampled shared users |
| Star Wars: Episode V - The Empire Strikes Back (1980) | Action\|Adventure\|Drama\|Sci-Fi\|War | 0.3369 | rating cosine: 123 sampled shared users |

结果说明系统已经能够达到原始仓库的核心功能：根据输入电影返回相似电影，并且具备可解释推荐结果。

### 6.2 抽样评估结果

当前一次抽样设置：

```text
sample_size = 10
k = 10
model = movie-cosine
```

实验结果如下：

| 指标 | 数值 |
| --- | ---: |
| Precision@10 | 0.0100 |
| Recall@10 | 0.1000 |
| NDCG@10 | 0.0500 |
| HitRate@10 | 0.1000 |
| Avg Latency | 1869.201 ms |
| p95 Latency | 9912.077 ms |

### 6.3 结果分析

从推荐效果看，当前抽样 HitRate@10 为 0.1，说明在 10 个抽样用户中有 1 个用户的隐藏目标电影被 Top-10 推荐命中。该指标不高，主要原因包括：

1. 当前方法是在线抽样版电影相似度计算，不是完整离线相似矩阵。
2. 抽样 leave-one-out 只保留一个目标电影，评价较严格。
3. MovieLens 32M 电影数量达到 87,618，候选空间较大。
4. 未训练 ALS/BPR 等矩阵分解模型，个性化能力有限。

从系统性能看，平均延迟约 1.87 秒，p95 延迟接近 9.91 秒，说明当前在线按需计算在大规模数据上存在明显性能瓶颈。这一结果也证明系统需要 Redis 缓存、离线预计算和模型服务化。

## 7. 当前问题与改进方向

### 7.1 热门电影偏置

从 Demo 推荐结果看，Matrix、Shawshank Redemption、Star Wars 等热门电影容易出现在结果前列。这说明评分共现和采样相似度容易受到热门电影影响。后续可通过以下方式改进：

1. 对高热电影进行流行度惩罚。
2. 使用调整余弦相似度或 Pearson 相似度。
3. 引入 BM25/TF-IDF 式的用户共现降权。
4. 使用 ALS/BPR 学习潜在向量，降低单纯共现带来的热门偏置。

### 7.2 响应延迟

当前相似度在线计算依赖 PostgreSQL 查询和 Python 聚合，在 32M 评分规模下 p95 延迟偏高。后续优化方向：

1. 离线预计算 Top-N 相似电影表。
2. 将相似度结果写入 Redis 或 PostgreSQL 物化表。
3. 对 `ratings(movie_id, user_id)` 和 `ratings(user_id, movie_id)` 建立合适索引。
4. 使用 implicit 模型训练 item factors，在线只做向量近邻检索。

### 7.3 实验完整性

当前 Evaluation 页面已经形成基本评估闭环，但仍属于抽样评估。若要达到更完整的论文实验标准，需要补充：

1. Popular、Item-CF、ALS、BPR、Hybrid 的横向对比。
2. RecBole 离线评估结果。
3. Spark ALS 分布式训练对照。
4. 缓存命中前后接口响应时间对比。
5. Docker CPU/内存占用记录。

## 8. 结论

本实验完成了一个基于 Docker Compose、FastAPI、Streamlit、PostgreSQL 和 Redis 的电影推荐系统 Demo。系统已经能够支持电影搜索、相似电影推荐、推荐解释、相似度得分、本地 Demo CTR 和抽样评估指标展示。

与原始 FastAPI Movie Recommender 仓库相比，当前系统至少达到了其核心能力，并在以下方面有所扩展：

1. 数据库从 SQLite 扩展到 PostgreSQL。
2. 数据规模从 MovieLens 100K/1M 扩展到 32M 级别。
3. 增加 Redis 缓存和容器化多服务部署。
4. 增加 Evaluation 页面和抽样离线指标。
5. 增加冷启动电影添加入口和 Demo CTR 展示。

当前系统已经适合作为课程项目 Demo 和阶段性实验平台。若要进一步达到校级论文或本科创新项目标准，下一阶段应重点完成离线预计算、ALS/BPR 模型训练、RecBole 评估和 Spark ALS 对照实验。
