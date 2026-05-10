# 系统级软件工程图（Mermaid）

以下图形基于当前仓库实现整理，覆盖前端、后端、数据库、`.h5ad` 数据文件、入库脚本与真实数据处理脚本。

对应代码入口：

- 前端入口：`frontend/src/main.jsx`、`frontend/src/App.jsx`
- API 与运行时服务：`backend/app/main.py`
- ORM 与数据库初始化：`backend/app/models.py`、`backend/app/database.py`
- 单细胞入库：`backend/scripts/ingest_h5ad.py`
- 全量装载与重命名：`backend/scripts/admin/load_target_inventory.py`
- 重置并重入库：`backend/scripts/admin/reset_and_ingest.py`

## 1. 系统结构图

```mermaid
%%{init: {'theme':'base','themeVariables': {'fontFamily':'PingFang SC, Microsoft YaHei, sans-serif','primaryColor':'#F6FBF8','primaryTextColor':'#18322D','primaryBorderColor':'#1F6B5D','lineColor':'#436C64','secondaryColor':'#E8F4F0','tertiaryColor':'#FFF8E8','clusterBkg':'#FAFCFB','clusterBorder':'#A7C9BF'}, 'flowchart': {'curve':'basis','htmlLabels': true}} }%%
flowchart LR
    U["研究人员 / 数据分析人员<br/>浏览器访问者"]

    subgraph FE["前端展示层"]
        FE1["React + Vite 单页应用<br/>样本目录 / 样本详情 / RNA-seq 检索 / 汇总 UMAP"]
    end

    subgraph BE["后端服务层"]
        BE1["FastAPI API<br/>样本查询 / 资产下载 / 嵌入读取 / 单细胞预览"]
        BE2["启动初始化<br/>init_db()"]
    end

    subgraph DAL["数据访问层"]
        DAL1["SQLAlchemy ORM / Session"]
        DAL2["Scanpy / AnnData 读取器"]
    end

    subgraph STORE["存储层"]
        DB[("PostgreSQL<br/>population_groups / samples / sample_data_assets / single_cell_cells / 统计视图")]
        H5[("不可变 .h5ad 文件库<br/>/data/...")]
        RAW[("Manifest / 原始下载目录 / 预处理产物")]
    end

    subgraph PIPE["离线数据管道"]
        P1["下载脚本<br/>find_cellxgene_pbmc.py<br/>download_recount3_bulk.R<br/>download_sra_fastq.py"]
        P2["预处理脚本<br/>preprocess_single_cell.py<br/>preprocess_bulk_recount3.py<br/>preprocess_geo_bulk.py"]
        P3["入库与装载脚本<br/>ingest_h5ad.py<br/>load_target_inventory.py<br/>reset_and_ingest.py"]
    end

    U <--> FE1
    FE1 <--> BE1
    BE1 -.启动时.-> BE2
    BE1 --> DAL1
    BE1 --> DAL2
    DAL1 <--> DB
    DAL2 <--> H5
    P1 --> RAW
    RAW --> P2
    P2 --> H5
    H5 --> P3
    P3 --> DB
    P3 --> H5

    classDef user fill:#FFF3D9,stroke:#C98B1D,color:#5E420C,stroke-width:1.5px;
    classDef store fill:#EDF7F3,stroke:#2C7A68,color:#17322D,stroke-width:1.5px;
    classDef pipe fill:#EEF3FF,stroke:#3F63A8,color:#1E2D52,stroke-width:1.5px;
    class U user;
    class DB,H5,RAW store;
    class P1,P2,P3 pipe;
```

## 2. 系统整体用例图

```mermaid
%%{init: {'theme':'base','themeVariables': {'fontFamily':'PingFang SC, Microsoft YaHei, sans-serif','primaryColor':'#F8FBFA','primaryTextColor':'#18322D','primaryBorderColor':'#1F6B5D','lineColor':'#4A7068','secondaryColor':'#E8F4F0','tertiaryColor':'#FFF7E6','clusterBkg':'#FBFDFC','clusterBorder':'#A7C9BF'}, 'flowchart': {'curve':'linear','htmlLabels': true}} }%%
flowchart LR
    A1(["研究人员"])
    A2(["数据管理员"])

    subgraph SYS["多组学仓库系统"]
        UC1(["浏览样本目录"])
        UC2(["按人群 / 组织 / 条件 / 数据类型筛选样本"])
        UC3(["查看样本详情与元数据"])
        UC4(["下载 FASTQ / bulk / h5ad 资产"])
        UC5(["检索单细胞索引行"])
        UC6(["预览表达矩阵子集"])
        UC7(["查看 UMAP / PCA 嵌入"])
        UC8(["装载单细胞与衍生 pseudobulk 数据"])
        UC9(["注册真实 bulk / FASTQ 资产"])
        UC10(["重置数据库并重新入库"])
        UC11(["统一重命名样本标题与描述"])
        UC12(["查看人群配额覆盖状态"])
    end

    A1 --> UC1
    A1 --> UC2
    A1 --> UC3
    A1 --> UC4
    A1 --> UC5
    A1 --> UC6
    A1 --> UC7
    A1 --> UC12

    A2 --> UC8
    A2 --> UC9
    A2 --> UC10
    A2 --> UC11
    A2 --> UC12

    UC5 --> UC6
    UC3 --> UC4
    UC3 --> UC7

    classDef actor fill:#FFF3D9,stroke:#C98B1D,color:#5E420C,stroke-width:1.5px;
    classDef usecase fill:#EEF7F3,stroke:#2B7A68,color:#17322D,stroke-width:1.2px;
    class A1,A2 actor;
    class UC1,UC2,UC3,UC4,UC5,UC6,UC7,UC8,UC9,UC10,UC11,UC12 usecase;
```

## 3. 功能流程图

说明：该图描述用户侧“单细胞检索与表达预览”功能流程，对应 `frontend/src/App.jsx` 中的 `SingleCellQuery` 与后端 `/single-cell/cells`、`/single-cell/data` 接口。

```mermaid
%%{init: {'theme':'base','themeVariables': {'fontFamily':'PingFang SC, Microsoft YaHei, sans-serif','primaryColor':'#F8FBFA','primaryTextColor':'#18322D','primaryBorderColor':'#1F6B5D','lineColor':'#4A7068','secondaryColor':'#E8F4F0','tertiaryColor':'#FFF8E8'}, 'flowchart': {'curve':'stepBefore','htmlLabels': true}} }%%
flowchart TD
    S([开始]) --> A["进入 RNA-seq 检索页"]
    A --> B["输入筛选条件<br/>cell_type / tissue / condition / group_code / sample_id"]
    B --> C["点击“执行检索”"]
    C --> D["前端请求 GET /single-cell/cells"]
    D --> E["后端联表过滤<br/>single_cell_cells + sample_data_assets + samples + population_groups"]
    E --> F["返回最多 200 条索引行"]
    F --> G["前端渲染结果表格"]
    G --> H["用户勾选待预览行"]
    H --> I{"是否来自同一 asset_id?"}
    I -- 是 --> J["保留当前多行选择"]
    I -- 否 --> K["前端仅保留新 asset 的选择"]
    J --> L["点击“预览数据”"]
    K --> L
    L --> M["前端请求 POST /single-cell/data<br/>{ asset_id, indices }"]
    M --> N["后端校验 asset / sample / 索引合法性"]
    N --> O["读取对应 .h5ad 并切片 subset = adata[indices, :]"]
    O --> P["返回 genes / expression / obs"]
    P --> Q["前端渲染表达预览表"]
    Q --> R([结束])

    classDef good fill:#EAF7F2,stroke:#2B7A68,color:#17322D,stroke-width:1.2px;
    classDef warn fill:#FFF3D9,stroke:#C98B1D,color:#5E420C,stroke-width:1.2px;
    classDef io fill:#EEF3FF,stroke:#3F63A8,color:#1E2D52,stroke-width:1.2px;
    class S,R good;
    class D,M io;
    class I warn;
```

## 4. 系统与外部实体交互图

```mermaid
%%{init: {'theme':'base','themeVariables': {'fontFamily':'PingFang SC, Microsoft YaHei, sans-serif','primaryColor':'#F8FBFA','primaryTextColor':'#18322D','primaryBorderColor':'#1F6B5D','lineColor':'#4A7068','secondaryColor':'#E8F4F0','tertiaryColor':'#FFF8E8'}, 'flowchart': {'curve':'basis','htmlLabels': true}} }%%
flowchart LR
    U1["研究人员<br/>浏览器用户"]
    U2["数据管理员<br/>运维 / 数据处理人员"]
    E1["公共数据源<br/>CELLxGENE / GEO / SRA / recount3"]
    E2["本地文件系统<br/>data/raw / data/manifests / data/processed / data/h5ad"]

    SYS["多组学仓库系统<br/>前端 + FastAPI + PostgreSQL + 入库脚本"]

    U1 -- 浏览 / 筛选 / 详情 / 下载 / 检索 / 预览 --> SYS
    SYS -- HTML / JSON / 文件下载 --> U1

    U2 -- 启动容器 / 执行脚本 / 重置入库 / 重命名样本 --> SYS
    SYS -- 装载结果 / 配额状态 / API 文档 --> U2

    E1 -- 原始数据与元数据 --> SYS
    SYS -- 下载脚本访问 --> E1

    E2 -- 读写 manifest / 原始文件 / 处理后 h5ad --> SYS
    SYS -- 生成索引 / 资产记录 / 备份文件 --> E2

    classDef actor fill:#FFF3D9,stroke:#C98B1D,color:#5E420C,stroke-width:1.4px;
    classDef entity fill:#EEF3FF,stroke:#3F63A8,color:#1E2D52,stroke-width:1.4px;
    classDef system fill:#EAF7F2,stroke:#2B7A68,color:#17322D,stroke-width:1.8px;
    class U1,U2 actor;
    class E1,E2 entity;
    class SYS system;
```

## 5. 架构设计包图

```mermaid
%%{init: {'theme':'base','themeVariables': {'fontFamily':'PingFang SC, Microsoft YaHei, sans-serif','primaryColor':'#FAFCFB','primaryTextColor':'#18322D','primaryBorderColor':'#1F6B5D','lineColor':'#4A7068','secondaryColor':'#E8F4F0','tertiaryColor':'#FFF8E8','clusterBkg':'#FBFDFC','clusterBorder':'#A7C9BF'}, 'flowchart': {'curve':'linear','htmlLabels': true}} }%%
flowchart TB
    subgraph PKG_FE["包：frontend"]
        FE_MAIN["main.jsx<br/>挂载 BrowserRouter"]
        FE_APP["App.jsx<br/>页面路由 / API 调用 / 交互逻辑"]
        FE_STYLE["styles.css<br/>界面样式"]
        FE_UMAP["public/combined-umaps.html<br/>独立汇总 UMAP 页面"]
    end

    subgraph PKG_APP["包：backend/app"]
        APP_CFG["config.py<br/>环境配置"]
        APP_DB["database.py<br/>引擎 / Session / 视图初始化"]
        APP_MODEL["models.py<br/>ORM 实体"]
        APP_SCHEMA["schemas.py<br/>Pydantic 响应模型"]
        APP_API["main.py<br/>FastAPI 路由"]
    end

    subgraph PKG_SCRIPT["包：backend/scripts"]
        SC_INGEST["ingest_h5ad.py<br/>单样本 h5ad 入库"]
        SC_ADMIN["admin/*<br/>load_target_inventory / reset_and_ingest / retitle_samples"]
        SC_PRE["preprocess/*<br/>单细胞 / bulk / GEO 预处理"]
        SC_DL["download/*<br/>公共数据发现与下载"]
        SC_REG["register_*<br/>资产注册脚本"]
    end

    subgraph PKG_DATA["包：data 与 sql"]
        DATA_SQL["backend/sql/schema.sql<br/>静态 SQL 参考"]
        DATA_FILES["data/*<br/>manifest / raw / processed / h5ad / backups"]
    end

    FE_MAIN --> FE_APP
    FE_APP --> APP_API
    FE_UMAP --> APP_API

    APP_CFG --> APP_DB
    APP_DB --> APP_MODEL
    APP_MODEL --> APP_SCHEMA
    APP_API --> APP_DB
    APP_API --> APP_MODEL
    APP_API --> APP_SCHEMA

    SC_DL --> SC_PRE
    SC_PRE --> DATA_FILES
    DATA_FILES --> SC_INGEST
    DATA_FILES --> SC_ADMIN
    SC_INGEST --> APP_MODEL
    SC_ADMIN --> APP_MODEL
    SC_REG --> APP_MODEL

    DATA_SQL -. 结构参考 .-> APP_MODEL

    classDef pkg fill:#EEF7F3,stroke:#2B7A68,color:#17322D,stroke-width:1.2px;
    classDef data fill:#EEF3FF,stroke:#3F63A8,color:#1E2D52,stroke-width:1.2px;
    class FE_MAIN,FE_APP,FE_STYLE,FE_UMAP,APP_CFG,APP_DB,APP_MODEL,APP_SCHEMA,APP_API,SC_INGEST,SC_ADMIN,SC_PRE,SC_DL,SC_REG pkg;
    class DATA_SQL,DATA_FILES data;
```

## 6. 数据流图

```mermaid
%%{init: {'theme':'base','themeVariables': {'fontFamily':'PingFang SC, Microsoft YaHei, sans-serif','primaryColor':'#F8FBFA','primaryTextColor':'#18322D','primaryBorderColor':'#1F6B5D','lineColor':'#4A7068','secondaryColor':'#E8F4F0','tertiaryColor':'#FFF8E8'}, 'flowchart': {'curve':'basis','htmlLabels': true}} }%%
flowchart LR
    E1["外部实体 E1<br/>研究人员"]
    E2["外部实体 E2<br/>数据管理员"]
    E3["外部实体 E3<br/>公共数据源"]

    P1["处理 P1<br/>下载与预处理"]
    P2["处理 P2<br/>h5ad 入库与资产注册"]
    P3["处理 P3<br/>API 查询服务"]
    P4["处理 P4<br/>h5ad 细胞矩阵 / 嵌入读取"]

    D1[("数据存储 D1<br/>Manifest / Raw / Processed 文件")]
    D2[("数据存储 D2<br/>PostgreSQL 元数据与索引")]
    D3[("数据存储 D3<br/>不可变 .h5ad 文件")]

    E3 -- 原始样本数据 / 元信息 --> P1
    E2 -- 触发脚本 / 选择 manifest --> P1
    P1 -- 预处理结果 --> D1
    D1 -- 处理后 h5ad / CSV / FASTQ 路径 --> P2
    P2 -- 样本、资产、细胞索引 --> D2
    P2 -- 标准化 h5ad --> D3

    E1 -- 浏览 / 筛选 / 检索请求 --> P3
    P3 -- 样本目录 / 详情 / 配额 / 索引行 --> E1
    P3 -- 结构化查询 --> D2
    D2 -- 元数据 / asset_id / obs_index --> P3

    P3 -- 细胞预览 / 嵌入读取请求 --> P4
    P4 -- 文件路径 / sample_id / asset_id --> D2
    D2 -- 资产路径 / 过滤上下文 --> P4
    P4 -- 读取矩阵 / embedding --> D3
    D3 -- 基因 / 表达矩阵 / 坐标 --> P4
    P4 -- 预览数据 / 嵌入点 --> P3

    classDef ext fill:#FFF3D9,stroke:#C98B1D,color:#5E420C,stroke-width:1.4px;
    classDef proc fill:#EAF7F2,stroke:#2B7A68,color:#17322D,stroke-width:1.4px;
    classDef store fill:#EEF3FF,stroke:#3F63A8,color:#1E2D52,stroke-width:1.4px;
    class E1,E2,E3 ext;
    class P1,P2,P3,P4 proc;
    class D1,D2,D3 store;
```

## 7. 业务流程图

说明：该图描述真实数据从发现、预处理、入库到可查询的业务闭环。

```mermaid
%%{init: {'theme':'base','themeVariables': {'fontFamily':'PingFang SC, Microsoft YaHei, sans-serif','primaryColor':'#FAFCFB','primaryTextColor':'#18322D','primaryBorderColor':'#1F6B5D','lineColor':'#4A7068','secondaryColor':'#E8F4F0','tertiaryColor':'#FFF8E8','clusterBkg':'#FBFDFC','clusterBorder':'#A7C9BF'}, 'flowchart': {'curve':'stepAfter','htmlLabels': true}} }%%
flowchart LR
    subgraph L1["泳道：数据管理员"]
        B1["选择来源与候选项目"]
        B2["审核 manifest 中选中样本"]
        B3["执行重置或装载命令"]
        B4["在前端验证结果"]
    end

    subgraph L2["泳道：下载 / 预处理脚本"]
        C1["发现候选数据<br/>CELLxGENE / recount3 / GEO / SRA"]
        C2["下载原始文件"]
        C3["预处理为规范化 h5ad / CSV / FASTQ"]
    end

    subgraph L3["泳道：入库脚本"]
        D1["读取处理后 h5ad / manifest"]
        D2["写入样本主数据"]
        D3["注册 bulk / FASTQ / h5ad 资产"]
        D4["构建 single_cell_cells 行级索引"]
        D5["生成人群覆盖统计视图"]
        D6["统一重命名样本标题与描述"]
    end

    subgraph L4["泳道：运行时系统"]
        E1["FastAPI 提供查询与下载接口"]
        E2["前端展示目录、详情、嵌入与表达预览"]
    end

    B1 --> C1 --> B2 --> C2 --> C3 --> B3 --> D1 --> D2 --> D3 --> D4 --> D5 --> D6 --> E1 --> E2 --> B4

    classDef lane fill:#EAF7F2,stroke:#2B7A68,color:#17322D,stroke-width:1.2px;
    classDef ops fill:#FFF3D9,stroke:#C98B1D,color:#5E420C,stroke-width:1.2px;
    class B1,B2,B3,B4 ops;
    class C1,C2,C3,D1,D2,D3,D4,D5,D6,E1,E2 lane;
```

## 8. 复杂功能时序图

说明：该图描述“单细胞表达预览”这一复杂功能的调用时序。

```mermaid
%%{init: {'theme':'base','themeVariables': {'fontFamily':'PingFang SC, Microsoft YaHei, sans-serif','primaryColor':'#F8FBFA','primaryTextColor':'#18322D','primaryBorderColor':'#1F6B5D','lineColor':'#4A7068','secondaryColor':'#E8F4F0','tertiaryColor':'#FFF8E8'}} }%%
sequenceDiagram
    autonumber
    actor U as 研究人员
    participant FE as React 前端
    participant API as FastAPI
    participant ORM as SQLAlchemy / ORM
    participant PG as PostgreSQL
    participant SC as Scanpy / AnnData
    participant H5 as .h5ad 文件

    U->>FE: 打开 RNA-seq 检索页并输入筛选条件
    FE->>API: GET /single-cell/cells
    API->>ORM: 构造联表查询
    ORM->>PG: 查询 single_cell_cells + assets + samples + groups
    PG-->>ORM: 返回索引行列表
    ORM-->>API: SingleCellResult[]
    API-->>FE: 返回检索结果
    FE-->>U: 展示可选索引行

    U->>FE: 选择同一 asset 的若干行并点击“预览数据”
    FE->>API: POST /single-cell/data { asset_id, indices }
    API->>ORM: get_single_cell_asset(asset_id)
    ORM->>PG: 查询 sample_data_assets 与 sample
    PG-->>ORM: 返回资产路径与 sample_id
    ORM-->>API: 返回 Sample + Asset
    API->>API: 校验 indices 非空且在 n_obs 范围内
    API->>SC: read_h5ad(file_path)
    SC->>H5: 打开目标 h5ad 文件
    H5-->>SC: 返回 AnnData
    API->>SC: subset = adata[indices, :]
    SC-->>API: genes + expression + obs
    API-->>FE: SingleCellDataResponse
    FE-->>U: 渲染表达预览表

    Note over FE,API: 前端只允许一次预览同一 asset_id 的多行数据
    Note over API,H5: 运行时只从 PostgreSQL 取元数据与索引，不存储完整表达矩阵
```

## 9. 类图

```mermaid
%%{init: {'theme':'base','themeVariables': {'fontFamily':'PingFang SC, Microsoft YaHei, sans-serif','primaryColor':'#F8FBFA','primaryTextColor':'#18322D','primaryBorderColor':'#1F6B5D','lineColor':'#4A7068','secondaryColor':'#E8F4F0','tertiaryColor':'#FFF8E8'}} }%%
classDiagram
    class PopulationGroup {
        +int group_id
        +str group_code
        +str group_name
        +int min_single_cell_samples
        +int min_bulk_samples
    }

    class Sample {
        +str sample_id
        +str sample_code
        +int group_id
        +str? subject_id
        +str? study_id
        +str? title
        +str? description
        +str? species
        +str? tissue
        +str? condition
        +str? collection_site
        +dict metadata_json
        +datetime created_at
    }

    class SampleDataAsset {
        +int asset_id
        +str sample_id
        +str modality
        +str file_format
        +str file_path
        +str file_name
        +int? size_bytes
        +str? checksum
        +str? source_url
        +bool is_active
        +dict metadata_json
        +datetime created_at
    }

    class SingleCellCell {
        +int asset_id
        +int obs_index
        +str? cell_type
        +str? cluster
        +str? sample_barcode
        +dict metadata_json
    }

    class SampleSummary {
        +str sample_id
        +str sample_code
        +PopulationGroupInfo group
        +bool has_fastq
        +bool has_single_cell
        +bool has_bulk
        +list modalities
        +int? single_cell_asset_id
        +int single_cell_cell_count
    }

    class SampleDetail {
        +list~SampleAsset~ assets
    }

    class EmbeddingResponse {
        +str sample_id
        +int asset_id
        +str basis
        +list~str~ available_bases
        +int total_points
        +int returned_points
        +bool is_sampled
        +list~EmbeddingPoint~ points
    }

    PopulationGroup "1" --> "0..*" Sample : 归属
    Sample "1" --> "0..*" SampleDataAsset : 拥有
    SampleDataAsset "1" --> "0..*" SingleCellCell : 索引

    SampleSummary <|-- SampleDetail
    SampleDataAsset ..> SampleSummary : 生成 modalities / 计数
    SingleCellCell ..> EmbeddingResponse : 生成点坐标 / 标签
```

