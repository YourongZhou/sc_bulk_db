# 系统级软件工程图（Mermaid 对照版）

本文件是第二版 Mermaid 图集，用于和 `docs/system-engineering-figures-mermaid.md` 对照。图的内容仍严格对应当前项目实现，但在布局、分层和节点组织上重新绘制。

## 1. 系统结构图

```mermaid
%%{init: {"theme":"base","themeVariables":{"fontFamily":"PingFang SC, Microsoft YaHei, sans-serif","primaryColor":"#F7FAF8","primaryTextColor":"#17322D","primaryBorderColor":"#2E6F63","lineColor":"#4C6B64","secondaryColor":"#EEF4F2","tertiaryColor":"#FFF6E5","clusterBkg":"#FBFCFB","clusterBorder":"#9DBDB4"},"flowchart":{"curve":"basis","htmlLabels":true}} }%%
flowchart TB
    User["研究人员<br/>浏览器用户"]

    subgraph Runtime["运行时系统"]
        Browser["React 前端<br/>样本目录 / 样本详情 / RNA-seq 检索 / 汇总 UMAP"]
        API["FastAPI 后端<br/>REST API / 文件下载 / h5ad 懒加载"]
        ORM["SQLAlchemy<br/>ORM 模型 / Session"]
        Scanpy["Scanpy<br/>AnnData 读取"]
    end

    subgraph Storage["数据存储"]
        PG[("PostgreSQL<br/>样本元数据 / 资产索引 / 细胞行索引 / 统计视图")]
        H5[("不可变 h5ad 文件<br/>表达矩阵 / obs / var / obsm")]
        Assets[("本地资产文件<br/>FASTQ / bulk TSV / bulk CSV")]
    end

    subgraph Pipeline["离线数据管道"]
        Discovery["数据发现与下载<br/>CELLxGENE / GEO / SRA / recount3"]
        Preprocess["数据预处理<br/>标准化 metadata / 生成 UMAP 或 PCA"]
        Ingest["入库与资产注册<br/>ingest_h5ad / load_target_inventory / register_*"]
        Retitle["样本展示重命名<br/>retitle_samples"]
    end

    User <--> Browser
    Browser <--> API
    API --> ORM
    API --> Scanpy
    ORM <--> PG
    Scanpy <--> H5
    API --> Assets

    Discovery --> Preprocess
    Preprocess --> H5
    Preprocess --> Assets
    H5 --> Ingest
    Assets --> Ingest
    Ingest --> PG
    Ingest --> Retitle
    Retitle --> PG

    classDef actor fill:#FFF2CC,stroke:#B7791F,color:#3F2C09,stroke-width:1.5px;
    classDef runtime fill:#EAF6F1,stroke:#2E6F63,color:#17322D,stroke-width:1.4px;
    classDef store fill:#EEF2FF,stroke:#4966A8,color:#1F2D50,stroke-width:1.4px;
    classDef pipe fill:#F7EFE6,stroke:#A05A2C,color:#4A2410,stroke-width:1.4px;
    class User actor;
    class Browser,API,ORM,Scanpy runtime;
    class PG,H5,Assets store;
    class Discovery,Preprocess,Ingest,Retitle pipe;
```

## 2. 系统整体用例图

```mermaid
%%{init: {"theme":"base","themeVariables":{"fontFamily":"PingFang SC, Microsoft YaHei, sans-serif","primaryColor":"#F8FBFA","primaryTextColor":"#17322D","primaryBorderColor":"#2E6F63","lineColor":"#4C6B64","secondaryColor":"#EEF4F2","tertiaryColor":"#FFF6E5"},"flowchart":{"curve":"linear","htmlLabels":true}} }%%
flowchart LR
    Researcher(["研究人员"])
    Admin(["数据管理员"])

    subgraph System["多组学数据仓库"]
        UC_Browse(["浏览样本目录"])
        UC_Filter(["筛选人群 / 组织 / 条件 / 数据类型"])
        UC_Detail(["查看样本详情"])
        UC_Download(["下载样本资产"])
        UC_Quota(["查看人群覆盖配额"])
        UC_Query(["检索单细胞行索引"])
        UC_Preview(["预览表达矩阵"])
        UC_Embedding(["查看 UMAP / PCA 嵌入"])
        UC_Discover(["发现并下载公共数据"])
        UC_Preprocess(["预处理为标准 h5ad 或资产文件"])
        UC_Ingest(["写入样本、资产与细胞索引"])
        UC_Reset(["清库、备份并重新入库"])
        UC_Retitle(["生成 Sample N 展示名称与描述"])
    end

    Researcher --> UC_Browse
    Researcher --> UC_Filter
    Researcher --> UC_Detail
    Researcher --> UC_Download
    Researcher --> UC_Quota
    Researcher --> UC_Query
    Researcher --> UC_Preview
    Researcher --> UC_Embedding

    Admin --> UC_Discover
    Admin --> UC_Preprocess
    Admin --> UC_Ingest
    Admin --> UC_Reset
    Admin --> UC_Retitle
    Admin --> UC_Quota

    UC_Filter --> UC_Browse
    UC_Detail --> UC_Download
    UC_Detail --> UC_Embedding
    UC_Query --> UC_Preview
    UC_Discover --> UC_Preprocess
    UC_Preprocess --> UC_Ingest
    UC_Ingest --> UC_Retitle

    classDef actor fill:#FFF2CC,stroke:#B7791F,color:#3F2C09,stroke-width:1.5px;
    classDef usecase fill:#EAF6F1,stroke:#2E6F63,color:#17322D,stroke-width:1.2px;
    class Researcher,Admin actor;
    class UC_Browse,UC_Filter,UC_Detail,UC_Download,UC_Quota,UC_Query,UC_Preview,UC_Embedding,UC_Discover,UC_Preprocess,UC_Ingest,UC_Reset,UC_Retitle usecase;
```

## 3. 功能流程图

该图聚焦“样本目录浏览到详情、下载与嵌入图查看”的用户功能路径。

```mermaid
%%{init: {"theme":"base","themeVariables":{"fontFamily":"PingFang SC, Microsoft YaHei, sans-serif","primaryColor":"#F8FBFA","primaryTextColor":"#17322D","primaryBorderColor":"#2E6F63","lineColor":"#4C6B64","secondaryColor":"#EEF4F2","tertiaryColor":"#FFF6E5"},"flowchart":{"curve":"basis","htmlLabels":true}} }%%
flowchart TD
    Start([开始]) --> Open["打开数据库总览页"]
    Open --> Load["前端并行加载<br/>/metadata/options<br/>/groups/quota-status<br/>/samples"]
    Load --> Render["渲染人群覆盖卡片与样本目录"]
    Render --> Filter{"用户是否设置筛选条件?"}
    Filter -- 是 --> RequestFiltered["请求 /samples?data_type&group_code&tissue&condition&species"]
    Filter -- 否 --> Browse["浏览当前样本列表"]
    RequestFiltered --> Browse
    Browse --> Select["点击某个 Sample N"]
    Select --> Detail["请求 /samples/{sample_id}"]
    Detail --> HasSC{"样本是否有 RNA-seq h5ad 资产?"}
    HasSC -- 是 --> Embedding["请求 /samples/{sample_id}/embedding<br/>读取 UMAP 或 PCA 坐标"]
    HasSC -- 否 --> MetadataOnly["仅展示元数据与可下载资产"]
    Embedding --> ShowDetail["展示样本详情、资产列表与嵌入图"]
    MetadataOnly --> ShowDetail
    ShowDetail --> Download{"用户是否下载资产?"}
    Download -- 是 --> File["请求 /samples/{sample_id}/assets/{asset_id}/download"]
    Download -- 否 --> End([结束])
    File --> End

    classDef start fill:#EAF6F1,stroke:#2E6F63,color:#17322D,stroke-width:1.4px;
    classDef decision fill:#FFF2CC,stroke:#B7791F,color:#3F2C09,stroke-width:1.4px;
    classDef api fill:#EEF2FF,stroke:#4966A8,color:#1F2D50,stroke-width:1.4px;
    class Start,End start;
    class Filter,HasSC,Download decision;
    class Load,RequestFiltered,Detail,Embedding,File api;
```

## 4. 系统与外部实体交互图

```mermaid
%%{init: {"theme":"base","themeVariables":{"fontFamily":"PingFang SC, Microsoft YaHei, sans-serif","primaryColor":"#F8FBFA","primaryTextColor":"#17322D","primaryBorderColor":"#2E6F63","lineColor":"#4C6B64","secondaryColor":"#EEF4F2","tertiaryColor":"#FFF6E5"},"flowchart":{"curve":"basis","htmlLabels":true}} }%%
flowchart TB
    subgraph Outside["系统外部"]
        R["研究人员"]
        O["数据管理员"]
        Public["公共数据平台<br/>CELLxGENE / GEO / SRA / recount3"]
        FS["宿主机文件系统<br/>data 目录"]
    end

    subgraph Inside["系统边界：多组学数据仓库"]
        Web["前端网站<br/>localhost:8080"]
        Backend["后端 API<br/>localhost:8000"]
        DB["PostgreSQL<br/>localhost:5432"]
        Scripts["脚本工具<br/>download / preprocess / ingest / admin"]
    end

    R -- 页面访问与交互 --> Web
    Web -- JSON 请求 / 文件下载请求 --> Backend
    Backend -- JSON 响应 / 文件响应 --> Web
    Web -- 展示结果 --> R

    O -- 执行容器命令与脚本 --> Scripts
    Scripts -- 读取 / 写入文件 --> FS
    Scripts -- 下载公共数据 --> Public
    Public -- 原始数据与元数据 --> Scripts
    Scripts -- 写入元数据与索引 --> DB

    Backend -- 查询样本与索引 --> DB
    DB -- 返回结构化元数据 --> Backend
    Backend -- 读取 h5ad / FASTQ / bulk 文件 --> FS

    classDef external fill:#FFF2CC,stroke:#B7791F,color:#3F2C09,stroke-width:1.4px;
    classDef internal fill:#EAF6F1,stroke:#2E6F63,color:#17322D,stroke-width:1.4px;
    classDef data fill:#EEF2FF,stroke:#4966A8,color:#1F2D50,stroke-width:1.4px;
    class R,O,Public external;
    class Web,Backend,Scripts internal;
    class DB,FS data;
```

## 5. 架构设计包图

```mermaid
%%{init: {"theme":"base","themeVariables":{"fontFamily":"PingFang SC, Microsoft YaHei, sans-serif","primaryColor":"#F8FBFA","primaryTextColor":"#17322D","primaryBorderColor":"#2E6F63","lineColor":"#4C6B64","secondaryColor":"#EEF4F2","tertiaryColor":"#FFF6E5","clusterBkg":"#FBFCFB","clusterBorder":"#9DBDB4"},"flowchart":{"curve":"linear","htmlLabels":true}} }%%
flowchart LR
    subgraph FE["frontend 包"]
        FE_Main["main.jsx<br/>React 挂载"]
        FE_App["App.jsx<br/>路由 / 状态 / API 请求"]
        FE_Static["public/combined-umaps.html<br/>独立 UMAP 汇总页"]
        FE_CSS["styles.css<br/>视觉样式"]
    end

    subgraph APP["backend/app 包"]
        Config["config.py<br/>环境变量与 CORS"]
        Database["database.py<br/>engine / SessionLocal / 统计视图"]
        Models["models.py<br/>ORM 表结构"]
        Schemas["schemas.py<br/>响应与请求 DTO"]
        Main["main.py<br/>FastAPI 路由与业务编排"]
    end

    subgraph SCRIPTS["backend/scripts 包"]
        Download["download/*<br/>公共数据发现与下载"]
        Preprocess["preprocess/*<br/>数据标准化与 h5ad 生成"]
        Ingest["ingest_h5ad.py<br/>样本和细胞索引入库"]
        Admin["admin/*<br/>全量装载 / 重置 / 重命名"]
        Register["register_*<br/>单独注册资产"]
    end

    subgraph DATA["数据与部署资源"]
        Docker["Dockerfile / docker-compose.yml<br/>服务编排"]
        SQL["backend/sql/schema.sql<br/>静态结构参考"]
        DataDir["data/*<br/>manifest / raw / h5ad / generated"]
    end

    FE_Main --> FE_App
    FE_App --> Main
    FE_Static --> Main
    FE_CSS --> FE_App

    Main --> Schemas
    Main --> Models
    Main --> Database
    Database --> Config
    Database --> Models
    SQL -. 对齐表结构 .-> Models

    Download --> DataDir
    DataDir --> Preprocess
    Preprocess --> DataDir
    DataDir --> Ingest
    Ingest --> Models
    Admin --> Ingest
    Admin --> Models
    Register --> Models
    Docker --> FE
    Docker --> APP

    classDef frontend fill:#EAF6F1,stroke:#2E6F63,color:#17322D,stroke-width:1.3px;
    classDef backend fill:#EEF2FF,stroke:#4966A8,color:#1F2D50,stroke-width:1.3px;
    classDef script fill:#F7EFE6,stroke:#A05A2C,color:#4A2410,stroke-width:1.3px;
    classDef data fill:#FFF2CC,stroke:#B7791F,color:#3F2C09,stroke-width:1.3px;
    class FE_Main,FE_App,FE_Static,FE_CSS frontend;
    class Config,Database,Models,Schemas,Main backend;
    class Download,Preprocess,Ingest,Admin,Register script;
    class Docker,SQL,DataDir data;
```

## 6. 数据库物理模型图

该图描述当前 PostgreSQL 物理表、主外键、唯一约束、检查约束、统计视图，以及数据库索引记录与外部文件资产之间的对应关系。表达矩阵本体不进入数据库，数据库只保存样本元数据、资产路径和单细胞行级索引。

```mermaid
%%{init: {"theme":"base","themeVariables":{"fontFamily":"PingFang SC, Microsoft YaHei, sans-serif","primaryColor":"#F8FBFA","primaryTextColor":"#17322D","primaryBorderColor":"#2E6F63","lineColor":"#4C6B64","secondaryColor":"#EEF4F2","tertiaryColor":"#FFF6E5","clusterBkg":"#FBFCFB","clusterBorder":"#9DBDB4"},"flowchart":{"curve":"basis","htmlLabels":true}} }%%
flowchart LR
    subgraph PhysicalDB["PostgreSQL 物理库：omics_demo"]
        direction TB

        subgraph CoreTables["核心物理表"]
            direction LR
            PG["<b>population_groups</b><br/>PK group_id INTEGER<br/>UK group_code TEXT<br/>group_name TEXT<br/>min_single_cell_samples INTEGER<br/>min_bulk_samples INTEGER"]
            S["<b>samples</b><br/>PK sample_id TEXT<br/>UK sample_code TEXT<br/>FK group_id -> population_groups.group_id<br/>subject_id / study_id TEXT<br/>title / description TEXT<br/>species / tissue / condition TEXT<br/>collection_site TEXT<br/>metadata JSON<br/>created_at TIMESTAMP"]
            A["<b>sample_data_assets</b><br/>PK asset_id INTEGER<br/>FK sample_id -> samples.sample_id ON DELETE CASCADE<br/>UK sample_id + modality<br/>modality TEXT CHECK fastq | single_cell_h5ad | bulk<br/>file_format TEXT CHECK fastq.gz | h5ad | csv | tsv | txt<br/>file_path / file_name TEXT<br/>size_bytes BIGINT<br/>checksum / source_url TEXT<br/>is_active BOOLEAN<br/>metadata JSON<br/>created_at TIMESTAMP"]
            C["<b>single_cell_cells</b><br/>PK asset_id + obs_index<br/>FK asset_id -> sample_data_assets.asset_id ON DELETE CASCADE<br/>obs_index INTEGER<br/>cell_type / cluster TEXT<br/>sample_barcode TEXT<br/>metadata JSON"]
        end

        subgraph DerivedViews["统计视图"]
            direction TB
            V1["<b>vw_group_modality_counts</b><br/>按人群分组统计 active 资产<br/>single_cell_sample_count<br/>bulk_sample_count<br/>fastq_sample_count"]
            V2["<b>vw_group_quota_status</b><br/>合并分组配额阈值<br/>single_cell_ok BOOLEAN<br/>bulk_ok BOOLEAN"]
        end
    end

    subgraph FileLayer["数据库外部文件层"]
        direction TB
        Fastq["FASTQ 文件<br/>原始测序资产"]
        Bulk["bulk 表达文件<br/>csv / tsv / txt"]
        H5["h5ad 文件<br/>X 表达矩阵 / obs / var / obsm"]
    end

    PG ==>|"1:N<br/>samples.group_id"| S
    S ==>|"1:N<br/>sample_data_assets.sample_id"| A
    A ==>|"1:N<br/>single_cell_cells.asset_id"| C

    PG -.->|"LEFT JOIN"| V1
    S -.->|"按 group_id 聚合"| V1
    A -.->|"按 modality + is_active 计数"| V1
    PG -.->|"配额阈值"| V2
    V1 -.->|"覆盖数量"| V2

    A -->|"file_path 指向 fastq.gz"| Fastq
    A -->|"file_path 指向 bulk 表"| Bulk
    A -->|"file_path 指向 h5ad"| H5
    C -->|"obs_index 映射 h5ad obs 行"| H5

    Note["设计边界<br/>PostgreSQL 保存可查询元数据和行索引<br/>表达矩阵、基因名和嵌入坐标保留在源 h5ad 文件中"]
    C -.->|"懒加载表达数据时使用 asset_id + obs_index"| Note
    H5 -.->|"由 FastAPI + Scanpy 按需读取"| Note

    classDef table fill:#EAF6F1,stroke:#2E6F63,color:#17322D,stroke-width:1.4px;
    classDef view fill:#FFF6E5,stroke:#B7791F,color:#3F2C09,stroke-width:1.4px;
    classDef file fill:#EEF2FF,stroke:#4966A8,color:#1F2D50,stroke-width:1.4px;
    classDef note fill:#F7EFE6,stroke:#A05A2C,color:#4A2410,stroke-width:1.4px;
    class PG,S,A,C table;
    class V1,V2 view;
    class Fastq,Bulk,H5 file;
    class Note note;
```

## 7. 数据流图

```mermaid
%%{init: {"theme":"base","themeVariables":{"fontFamily":"PingFang SC, Microsoft YaHei, sans-serif","primaryColor":"#F8FBFA","primaryTextColor":"#17322D","primaryBorderColor":"#2E6F63","lineColor":"#4C6B64","secondaryColor":"#EEF4F2","tertiaryColor":"#FFF6E5"},"flowchart":{"curve":"basis","htmlLabels":true}} }%%
flowchart TB
    Source["公共数据源或本地原始数据"]
    Manifest[("manifest 文件<br/>候选样本与下载信息")]
    Raw[("raw 文件<br/>FASTQ / count matrix / SOFT metadata")]
    Processed[("processed 文件<br/>规范化 h5ad / bulk 表")]
    H5[("h5ad 文件<br/>X / obs / var / obsm")]
    DB[("PostgreSQL<br/>样本 / 资产 / 细胞索引 / 统计视图")]
    API["FastAPI 查询服务"]
    UI["React 前端展示"]
    User["研究人员"]

    Source -->|"发现候选"| Manifest
    Manifest -->|"下载选择"| Raw
    Raw -->|"预处理"| Processed
    Processed -->|"写入或生成"| H5
    H5 -->|"读取 obs 与元数据"| DB
    Processed -->|"注册 bulk / FASTQ 文件路径"| DB
    DB -->|"样本列表 / 详情 / 配额 / 索引行"| API
    H5 -->|"表达矩阵切片 / UMAP / PCA"| API
    API -->|"JSON / 文件响应"| UI
    UI -->|"可视化与表格"| User
    User -->|"筛选 / 检索 / 下载 / 预览"| UI

    classDef source fill:#FFF2CC,stroke:#B7791F,color:#3F2C09,stroke-width:1.3px;
    classDef store fill:#EEF2FF,stroke:#4966A8,color:#1F2D50,stroke-width:1.3px;
    classDef app fill:#EAF6F1,stroke:#2E6F63,color:#17322D,stroke-width:1.3px;
    class Source,User source;
    class Manifest,Raw,Processed,H5,DB store;
    class API,UI app;
```

## 8. 业务流程图

```mermaid
%%{init: {"theme":"base","themeVariables":{"fontFamily":"PingFang SC, Microsoft YaHei, sans-serif","primaryColor":"#F8FBFA","primaryTextColor":"#17322D","primaryBorderColor":"#2E6F63","lineColor":"#4C6B64","secondaryColor":"#EEF4F2","tertiaryColor":"#FFF6E5","clusterBkg":"#FBFCFB","clusterBorder":"#9DBDB4"},"flowchart":{"curve":"stepAfter","htmlLabels":true}} }%%
flowchart LR
    subgraph A["阶段一：数据准备"]
        A1["发现或选择数据源"]
        A2["生成 manifest"]
        A3["审核 selected 样本"]
        A4["下载原始数据"]
    end

    subgraph B["阶段二：标准化处理"]
        B1["单细胞数据标准化 obs / metadata"]
        B2["bulk 数据转换为可入库格式"]
        B3["计算或保留 UMAP / PCA"]
        B4["输出 processed h5ad 或资产文件"]
    end

    subgraph C["阶段三：仓库入库"]
        C1["初始化数据库结构与人群分组"]
        C2["写入 samples"]
        C3["写入 sample_data_assets"]
        C4["写入 single_cell_cells 行索引"]
        C5["刷新人群覆盖统计视图"]
        C6["生成 Sample N 展示标题和环境描述"]
    end

    subgraph D["阶段四：用户使用"]
        D1["浏览样本目录"]
        D2["按人群与数据类型筛选"]
        D3["查看详情和下载资产"]
        D4["检索单细胞行"]
        D5["预览表达矩阵或查看嵌入图"]
    end

    A1 --> A2 --> A3 --> A4 --> B1
    A4 --> B2
    B1 --> B3 --> B4
    B2 --> B4
    B4 --> C1 --> C2 --> C3 --> C4 --> C5 --> C6 --> D1
    D1 --> D2 --> D3
    D2 --> D4 --> D5
    D3 --> D5

    classDef prep fill:#FFF2CC,stroke:#B7791F,color:#3F2C09,stroke-width:1.3px;
    classDef norm fill:#F7EFE6,stroke:#A05A2C,color:#4A2410,stroke-width:1.3px;
    classDef ingest fill:#EEF2FF,stroke:#4966A8,color:#1F2D50,stroke-width:1.3px;
    classDef use fill:#EAF6F1,stroke:#2E6F63,color:#17322D,stroke-width:1.3px;
    class A1,A2,A3,A4 prep;
    class B1,B2,B3,B4 norm;
    class C1,C2,C3,C4,C5,C6 ingest;
    class D1,D2,D3,D4,D5 use;
```

## 9. 复杂功能时序图

该图描述“打开样本详情并加载嵌入图”的时序，对应 `/samples/{sample_id}` 与 `/samples/{sample_id}/embedding`。

```mermaid
%%{init: {"theme":"base","themeVariables":{"fontFamily":"PingFang SC, Microsoft YaHei, sans-serif","primaryColor":"#F8FBFA","primaryTextColor":"#17322D","primaryBorderColor":"#2E6F63","lineColor":"#4C6B64","secondaryColor":"#EEF4F2","tertiaryColor":"#FFF6E5"}} }%%
sequenceDiagram
    autonumber
    actor User as 研究人员
    participant FE as React 前端
    participant API as FastAPI
    participant ORM as SQLAlchemy
    participant DB as PostgreSQL
    participant Scanpy as Scanpy
    participant H5 as h5ad 文件

    User->>FE: 点击样本卡片 Sample N
    FE->>API: GET /samples/{sample_id}
    API->>ORM: 查询 Sample 并预加载 group 与 assets
    ORM->>DB: SELECT samples + population_groups + sample_data_assets
    DB-->>ORM: 返回样本、分组与资产记录
    ORM-->>API: ORM 对象
    API->>API: serialize_sample() 与 serialize_asset()
    API-->>FE: SampleDetail
    FE-->>User: 展示标题、描述、标签、资产列表

    alt 样本包含 RNA-seq h5ad 资产
        FE->>API: GET /samples/{sample_id}/embedding?basis=umap
        API->>ORM: get_single_cell_asset(sample_id)
        ORM->>DB: 查询 active single_cell_h5ad 资产
        DB-->>ORM: 返回 asset.file_path
        ORM-->>API: Sample + Asset
        API->>Scanpy: read_h5ad(file_path, backed="r")
        Scanpy->>H5: 读取 obsm 与 obs
        H5-->>Scanpy: X_umap 或 X_pca 坐标
        API->>API: 按 max_points 采样并组装 EmbeddingPoint
        API-->>FE: EmbeddingResponse
        FE-->>User: 渲染 UMAP / PCA 散点图
    else 样本没有 RNA-seq h5ad 资产
        FE-->>User: 仅展示元数据与可下载资产
    end

    Note over API,H5: 表达矩阵和嵌入坐标保留在 h5ad 文件中，数据库只保存可检索索引和路径
```

## 10. 类图

```mermaid
%%{init: {"theme":"base","themeVariables":{"fontFamily":"PingFang SC, Microsoft YaHei, sans-serif","primaryColor":"#F8FBFA","primaryTextColor":"#17322D","primaryBorderColor":"#2E6F63","lineColor":"#4C6B64","secondaryColor":"#EEF4F2","tertiaryColor":"#FFF6E5"}} }%%
classDiagram
    direction LR

    class PopulationGroup {
        +Integer group_id
        +Text group_code
        +Text group_name
        +Integer min_single_cell_samples
        +Integer min_bulk_samples
    }

    class Sample {
        +Text sample_id
        +Text sample_code
        +Integer group_id
        +Text subject_id
        +Text study_id
        +Text title
        +Text description
        +Text species
        +Text tissue
        +Text condition
        +Text collection_site
        +JSON metadata_json
        +DateTime created_at
    }

    class SampleDataAsset {
        +Integer asset_id
        +Text sample_id
        +Text modality
        +Text file_format
        +Text file_path
        +Text file_name
        +BigInteger size_bytes
        +Text checksum
        +Text source_url
        +Boolean is_active
        +JSON metadata_json
        +DateTime created_at
    }

    class SingleCellCell {
        +Integer asset_id
        +Integer obs_index
        +Text cell_type
        +Text cluster
        +Text sample_barcode
        +JSON metadata_json
    }

    class SampleSummaryDTO {
        +String sample_id
        +String sample_code
        +PopulationGroupInfo group
        +Boolean has_fastq
        +Boolean has_single_cell
        +Boolean has_bulk
        +String[] modalities
        +Integer single_cell_cell_count
    }

    class SampleDetailDTO {
        +SampleAsset[] assets
    }

    class SingleCellDataResponseDTO {
        +Integer asset_id
        +String sample_id
        +Integer[] indices
        +String[] genes
        +Float[][] expression
        +Object[] obs
    }

    class EmbeddingResponseDTO {
        +String sample_id
        +Integer asset_id
        +String basis
        +String[] available_bases
        +Integer total_points
        +Integer returned_points
        +Boolean is_sampled
        +EmbeddingPoint[] points
    }

    PopulationGroup "1" --> "0..*" Sample : 分组包含样本
    Sample "1" --> "0..*" SampleDataAsset : 样本拥有资产
    SampleDataAsset "1" --> "0..*" SingleCellCell : h5ad 资产建立行索引

    SampleSummaryDTO <|-- SampleDetailDTO
    Sample --> SampleSummaryDTO : 序列化
    SampleDataAsset --> SampleDetailDTO : 序列化
    SingleCellCell --> SingleCellDataResponseDTO : 选择 obs_index
    SampleDataAsset --> EmbeddingResponseDTO : 定位 h5ad 文件
```
